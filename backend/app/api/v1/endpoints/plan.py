from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.plan import AICreditLedgerEntry, Plan, ShopSubscription
from app.models.team_member import TeamMember, TeamRole
from app.schemas.plan import PlanChangeRequest, PlanOut, ShopPlanOut

router = APIRouter(prefix="/plan", tags=["plan"])


@router.get("/catalogue", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    return db.query(Plan).all()


@router.get("", response_model=ShopPlanOut)
def get_my_plan(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ShopPlanOut:
    subscription = (
        db.query(ShopSubscription).filter(ShopSubscription.shop_id == current_user.shop_id).first()
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription on record for this shop")

    entries = (
        db.query(AICreditLedgerEntry)
        .filter(AICreditLedgerEntry.shop_id == current_user.shop_id, AICreditLedgerEntry.kind == "text_credit")
        .with_entities(AICreditLedgerEntry.amount)
        .all()
    )
    used = sum((-e[0] for e in entries if e[0] < 0), Decimal("0"))
    granted = sum((e[0] for e in entries if e[0] > 0), Decimal("0"))

    return ShopPlanOut(
        plan_code=subscription.plan_code,
        status=subscription.status,
        renews_at=subscription.renews_at,
        ai_credits_used_this_month=used,
        ai_credits_remaining=granted - used,
    )


@router.post("/change", response_model=ShopPlanOut)
def change_plan(
    payload: PlanChangeRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> ShopPlanOut:
    subscription = (
        db.query(ShopSubscription).filter(ShopSubscription.shop_id == current_user.shop_id).first()
    )
    if subscription is None:
        subscription = ShopSubscription(shop_id=current_user.shop_id, plan_code=payload.plan_code)
    else:
        subscription.plan_code = payload.plan_code
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return ShopPlanOut(
        plan_code=subscription.plan_code,
        status=subscription.status,
        renews_at=subscription.renews_at,
        ai_credits_used_this_month=Decimal("0"),
        ai_credits_remaining=Decimal("0"),
    )
