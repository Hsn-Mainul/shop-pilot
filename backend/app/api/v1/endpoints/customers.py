import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.models.team_member import TeamMember, TeamRole
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.schemas.review import ReviewCreate, ReviewOut

router = APIRouter(prefix="/customers", tags=["customers"])

# FR-CUST-02 segmentation thresholds: tune later from real data.
VIP_ORDER_COUNT = 5
REPEAT_ORDER_COUNT = 2


@router.get("", response_model=list[CustomerOut])
def list_customers(
    q: str | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    query = db.query(Customer).filter(Customer.shop_id == current_user.shop_id)
    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%") | Customer.phone.ilike(f"%{q}%"))
    customers = query.order_by(Customer.created_at.desc()).all()

    # Attach order counts in one query rather than N+1
    customer_ids = [c.id for c in customers]
    order_counts: dict[uuid.UUID, int] = {}
    if customer_ids:
        rows = (
            db.query(Order.customer_id, func.count(Order.id))
            .filter(Order.customer_id.in_(customer_ids))
            .group_by(Order.customer_id)
            .all()
        )
        order_counts = {row[0]: row[1] for row in rows}

    result = []
    for c in customers:
        out = CustomerOut.model_validate(c)
        out.order_count = order_counts.get(c.id, 0)
        result.append(out)
    return result


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = Customer(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _get_owned_customer(customer_id: uuid.UUID, current_user: TeamMember, db: Session) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.shop_id == current_user.shop_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = _get_owned_customer(customer_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/enrich-names", response_model=dict)
def enrich_customer_names(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Back-fill real display names AND real phone numbers for existing customers.

    - Names: fetched from the Graph API for Facebook/Instagram users still
      identified only by a raw numeric PSID.
    - Phones: copied from Order.customer_phone for any customer whose phone
      field is still an internal identity key (fb:xxx etc.) but who has placed
      at least one order with a real phone number.
    """
    import re as _re
    from app.integrations.meta_graph import fetch_messenger_user_name
    from app.models.conversation import Conversation, ConversationChannel
    from app.models.integration import Integration, IntegrationStatus

    _IDENTITY_RE = _re.compile(r"^(fb|ig|wa|tg|cmt|wh|ch):", _re.I)
    phones_updated = 0
    names_updated = 0

    # ── Step 1: back-fill phones from orders ─────────────────────────────────
    phone_rows = (
        db.query(Customer, Order.customer_phone)
        .join(Order, Order.customer_id == Customer.id)
        .filter(
            Customer.shop_id == current_user.shop_id,
            Order.customer_phone.isnot(None),
        )
        .all()
    )
    seen_ids: set[uuid.UUID] = set()
    for customer, order_phone in phone_rows:
        if customer.id in seen_ids:
            continue
        seen_ids.add(customer.id)
        if _IDENTITY_RE.match(customer.phone or "") and order_phone and order_phone.strip():
            # Store in email field — never overwrite phone (it's the PSID identity key)
            current_email = customer.email or ""
            email_is_placeholder = not current_email or current_email.startswith("page:") or current_email.startswith("comment:")
            if email_is_placeholder:
                customer.email = order_phone.strip()
                db.add(customer)
                phones_updated += 1

    # ── Step 2: back-fill names from Graph API ────────────────────────────────
    # Build page_id → token map
    token_map: dict[str, str] = {}
    for provider in ("facebook", "instagram"):
        for integ in (
            db.query(Integration)
            .filter(
                Integration.shop_id == current_user.shop_id,
                Integration.provider == provider,
                Integration.status == IntegrationStatus.CONNECTED,
            )
            .all()
        ):
            cfg = integ.config or {}
            pid = str(cfg.get("page_id") or "")
            tok = cfg.get("page_access_token")
            if pid and tok:
                token_map[pid] = tok
            for p in cfg.get("pages") or []:
                if p.get("id") and p.get("access_token"):
                    token_map[str(p["id"])] = p["access_token"]

    if token_map:
        unknown = (
            db.query(Customer)
            .filter(
                Customer.shop_id == current_user.shop_id,
                Customer.phone.like("fb:%"),
            )
            .filter(
                (Customer.name.is_(None))
                | Customer.name.op("~")(r"^\d{10,}$")
            )
            .limit(50)
            .all()
        )

        for customer in unknown:
            psid = (customer.phone or "").removeprefix("fb:").split(":")[0]
            if not psid:
                continue
            conv = (
                db.query(Conversation)
                .filter(
                    Conversation.customer_id == customer.id,
                    Conversation.channel.in_([ConversationChannel.FACEBOOK, ConversationChannel.INSTAGRAM]),
                )
                .first()
            )
            page_id = conv.page_id if conv else None
            token = token_map.get(page_id or "") if page_id else next(iter(token_map.values()), None)
            if not token:
                continue
            try:
                real_name = fetch_messenger_user_name(psid, token)
                if real_name and not _re.match(r"^\d+$", real_name):
                    customer.name = real_name
                    db.add(customer)
                    names_updated += 1
            except Exception:
                continue

    db.commit()
    parts = []
    if phones_updated:
        parts.append(f"{phones_updated} phone number(s) resolved from orders")
    if names_updated:
        parts.append(f"{names_updated} name(s) resolved from Facebook")
    if not parts:
        parts.append("everything already up to date")
    return {"updated": phones_updated + names_updated, "message": ", ".join(parts).capitalize() + "."}


@router.post("/segments/recompute", response_model=list[CustomerOut])
def recompute_segments(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    """Score every customer with a delivered order into a segment (FR-CUST-02)."""
    delivered_counts = Counter(
        row.customer_id
        for row in db.query(Order.customer_id)
        .filter(Order.shop_id == current_user.shop_id, Order.status == OrderStatus.DELIVERED)
        .all()
    )
    customers = db.query(Customer).filter(Customer.shop_id == current_user.shop_id).all()
    for customer in customers:
        count = delivered_counts.get(customer.id, 0)
        if count >= VIP_ORDER_COUNT:
            customer.segment = "vip"
        elif count >= REPEAT_ORDER_COUNT:
            customer.segment = "repeat_customer"
        elif count == 1:
            customer.segment = "one_time_customer"
        else:
            customer.segment = "no_orders_yet"
        db.add(customer)
    db.commit()
    return customers


@router.patch("/{customer_id}/block", response_model=CustomerOut)
def toggle_block_customer(
    customer_id: uuid.UUID,
    blocked: bool = True,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = _get_owned_customer(customer_id, current_user, db)
    customer.is_blocked = blocked
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


reviews_router = APIRouter(prefix="/reviews", tags=["customers"])


@reviews_router.get("", response_model=list[ReviewOut])
def list_reviews(
    include_hidden: bool = False,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewOut]:
    query = db.query(Review).join(Customer).filter(Customer.shop_id == current_user.shop_id)
    if not include_hidden:
        query = query.filter(Review.is_hidden.is_(False))
    return query.order_by(Review.created_at.desc()).all()


@reviews_router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    customer = _get_owned_customer(payload.customer_id, current_user, db)
    review = Review(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@reviews_router.patch("/{review_id}/hide", response_model=ReviewOut)
def hide_review(
    review_id: uuid.UUID,
    hidden: bool = True,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> ReviewOut:
    review = (
        db.query(Review)
        .filter(Review.id == review_id, Review.shop_id == current_user.shop_id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    review.is_hidden = hidden
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
