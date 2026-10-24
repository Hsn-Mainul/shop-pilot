import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.core.security import hash_password
from app.models.integration import Integration, IntegrationStatus
from app.models.product import Product
from app.models.team_member import TeamMember, TeamRole
from app.schemas.shop import (
    SetupChecklistOut,
    SetupChecklistStep,
    ShopOut,
    ShopUpdate,
    TeamMemberInvite,
    TeamMemberOut,
)

router = APIRouter(tags=["shops"])


@router.get("/shops/me", response_model=ShopOut)
def get_my_shop(current_user: TeamMember = Depends(get_current_user), db: Session = Depends(get_db)) -> ShopOut:
    shop = current_user.shop
    return shop


@router.patch("/shops/me", response_model=ShopOut)
def update_my_shop(
    payload: ShopUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShopOut:
    shop = current_user.shop
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/team-members", response_model=list[TeamMemberOut])
def list_team_members(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)), db: Session = Depends(get_db)
) -> list[TeamMemberOut]:
    return db.query(TeamMember).filter(TeamMember.shop_id == current_user.shop_id).all()


@router.get("/shops/me/setup-checklist", response_model=SetupChecklistOut)
def get_setup_checklist(
    current_user: TeamMember = Depends(get_current_user), db: Session = Depends(get_db)
) -> SetupChecklistOut:
    """FR-SET-01/04: live progress computed from what's actually on record, not a stored flag."""
    shop = current_user.shop
    has_products = db.query(Product).filter(Product.shop_id == shop.id).first() is not None
    has_connected_channel = (
        db.query(Integration)
        .filter(Integration.shop_id == shop.id, Integration.status == IntegrationStatus.CONNECTED)
        .first()
        is not None
    )
    payment_config = (shop.ai_module_toggles or {}).get("payment_methods", {})
    has_payment_configured = (
        shop.delivery_charge_inside_city is not None
        or bool(payment_config.get("bkash_number"))
        or bool(payment_config.get("nagad_number"))
        or bool(payment_config.get("bank_details"))
    )
    has_logo = bool((shop.ai_module_toggles or {}).get("logo_url"))
    team_count = db.query(TeamMember).filter(TeamMember.shop_id == shop.id).count()

    steps = [
        SetupChecklistStep(
            key="logo_and_shop_name", label="Logo and Shop Name", group="your_shop",
            is_done=bool(shop.name), estimated_minutes=1,
        ),
        SetupChecklistStep(
            key="address_and_delivery_charges", label="Address and Delivery Charges", group="your_shop",
            is_done=bool(shop.address) and shop.delivery_charge_inside_city is not None, estimated_minutes=2,
        ),
        SetupChecklistStep(
            key="add_first_products", label="Add Your First 5 Products", group="products",
            is_done=has_products, estimated_minutes=5,
        ),
        SetupChecklistStep(
            key="connect_facebook_page", label="Connect Your Facebook Page", group="get_orders",
            is_done=has_connected_channel, estimated_minutes=2,
        ),
        SetupChecklistStep(
            key="how_you_get_paid", label="How You Get Paid", group="get_paid",
            is_done=has_payment_configured, estimated_minutes=2,
        ),
        SetupChecklistStep(
            key="teach_ai_how_shop_works", label="Teach The AI How Your Shop Works", group="ai_assistant",
            is_done=bool(shop.opening_hours), estimated_minutes=4,
        ),
        SetupChecklistStep(
            key="invite_a_teammate", label="Invite a Teammate", group="team",
            is_done=team_count > 1, estimated_minutes=1,
        ),
    ]
    steps_done = sum(1 for s in steps if s.is_done)
    up_next = next((s for s in steps if not s.is_done), None)
    return SetupChecklistOut(
        percent_complete=int(100 * steps_done / len(steps)),
        steps_done=steps_done,
        steps_total=len(steps),
        up_next=up_next,
        steps=steps,
    )


@router.post("/team-members/invite", response_model=TeamMemberOut, status_code=status.HTTP_201_CREATED)
def invite_team_member(
    payload: TeamMemberInvite,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> TeamMemberOut:
    """FR-TEAM-02: invite a teammate by email with a pre-assigned role.

    Creates the account with a temporary password and emails credentials when
    SMTP is configured (settings.smtp_*).
    """
    from app.integrations.messaging import MessagingNotConfiguredError, send_email

    existing = db.query(TeamMember).filter(TeamMember.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    try:
        role = TeamRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role '{payload.role}'")
    if role == TeamRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invite a second Super Admin")

    temporary_password = secrets.token_urlsafe(12)
    member = TeamMember(
        shop_id=current_user.shop_id,
        email=payload.email,
        hashed_password=hash_password(temporary_password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    shop_name = current_user.shop.name
    try:
        send_email(
            payload.email,
            subject=f"You're invited to {shop_name}",
            body=(
                f"Hi {payload.first_name or 'there'},\n\n"
                f"You've been invited to join {shop_name} as {role.value}.\n"
                f"Sign in with:\n  Email: {payload.email}\n  Temporary password: {temporary_password}\n\n"
                "Please change your password after first login.\n"
            ),
        )
    except MessagingNotConfiguredError:
        # Account still created; admin can share the temp password manually.
        pass

    return member
