import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.automation import AutomationKind, AutomationRule, BulkCampaign, CustomerChannelOptOut
from app.models.customer import Customer
from app.models.team_member import TeamMember, TeamRole
from app.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleOut,
    BulkCampaignCreate,
    BulkCampaignOut,
    RecipeInstallRequest,
    RecipeOut,
)
from app.tasks.campaign_tasks import send_campaign

router = APIRouter(tags=["automation"])

PREBUILT_RECIPES = [
    {
        "code": "low_stock_alert",
        "name": "Low stock alert",
        "description": "Open a support ticket when stock hits the reorder point.",
        "trigger": "stock.low",
        "action": "create_support_request",
        "config": {"subject": "Low stock alert"},
    },
    {
        "code": "auto_reply_inbound",
        "name": "Auto-reply on inbound message",
        "description": "Send a saved reply when a customer messages you.",
        "trigger": "message.received",
        "action": "send_saved_reply",
        "config": {},
    },
    {
        "code": "cod_confirm_call",
        "name": "COD confirm call",
        "description": "Flag high-value COD orders for an outbound confirmation call.",
        "trigger": "order.confirmed",
        "action": "create_support_request",
        "config": {"subject": "Confirm COD order by call", "min_total": 2000},
    },
    {
        "code": "comment_auto_reply",
        "name": "Comment auto-reply",
        "description": "Reply to public comments with a thank-you template.",
        "trigger": "message.received",
        "action": "send_saved_reply",
        "config": {"channels": ["comment"]},
    },
]


@router.get("/automations/recipes", response_model=list[RecipeOut])
def list_recipes(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[RecipeOut]:
    installed = {
        r.name
        for r in db.query(AutomationRule)
        .filter(AutomationRule.shop_id == current_user.shop_id, AutomationRule.kind == AutomationKind.RECIPE)
        .all()
    }
    return [
        RecipeOut(
            **recipe,
            installed=recipe["name"] in installed,
        )
        for recipe in PREBUILT_RECIPES
    ]


@router.post("/automations/recipes/install", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
def install_recipe(
    payload: RecipeInstallRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> AutomationRuleOut:
    recipe = next((r for r in PREBUILT_RECIPES if r["code"] == payload.code), None)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    existing = (
        db.query(AutomationRule)
        .filter(
            AutomationRule.shop_id == current_user.shop_id,
            AutomationRule.kind == AutomationKind.RECIPE,
            AutomationRule.name == recipe["name"],
        )
        .first()
    )
    if existing:
        return existing
    rule = AutomationRule(
        shop_id=current_user.shop_id,
        kind=AutomationKind.RECIPE,
        name=recipe["name"],
        trigger=recipe["trigger"],
        action=recipe["action"],
        config=recipe["config"],
        is_active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/automations/rules", response_model=list[AutomationRuleOut])
def list_rules(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AutomationRuleOut]:
    return db.query(AutomationRule).filter(AutomationRule.shop_id == current_user.shop_id).all()


@router.post("/automations/rules", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: AutomationRuleCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> AutomationRuleOut:
    rule = AutomationRule(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/automations/rules/{rule_id}/toggle", response_model=AutomationRuleOut)
def toggle_rule(
    rule_id: uuid.UUID,
    is_active: bool,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> AutomationRuleOut:
    rule = (
        db.query(AutomationRule)
        .filter(AutomationRule.id == rule_id, AutomationRule.shop_id == current_user.shop_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    rule.is_active = is_active
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/campaigns", response_model=list[BulkCampaignOut])
def list_campaigns(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[BulkCampaignOut]:
    return (
        db.query(BulkCampaign)
        .filter(BulkCampaign.shop_id == current_user.shop_id)
        .order_by(BulkCampaign.created_at.desc())
        .limit(50)
        .all()
    )


@router.post("/campaigns/bulk-message", response_model=BulkCampaignOut, status_code=status.HTTP_201_CREATED)
def create_bulk_campaign(
    payload: BulkCampaignCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> BulkCampaignOut:
    opted_out_count = (
        db.query(CustomerChannelOptOut)
        .join(Customer)
        .filter(Customer.shop_id == current_user.shop_id, CustomerChannelOptOut.channel == payload.channel)
        .count()
    )
    campaign = BulkCampaign(
        shop_id=current_user.shop_id,
        **payload.model_dump(),
        status="scheduled" if payload.scheduled_at else "sending",
        opted_out_excluded_count=opted_out_count,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # FR-CUST-06/07: genuinely dispatch via Celery (app/tasks/campaign_tasks.py),
    # which sends real email/SMS/WhatsApp/voice through the configured provider
    # and updates sent_count/delivered_count/status when it finishes.
    if not payload.scheduled_at:
        send_campaign.delay(str(campaign.id))

    return campaign


@router.get("/campaigns/{campaign_id}/report", response_model=BulkCampaignOut)
def campaign_report(
    campaign_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> BulkCampaignOut:
    campaign = (
        db.query(BulkCampaign)
        .filter(BulkCampaign.id == campaign_id, BulkCampaign.shop_id == current_user.shop_id)
        .first()
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign
