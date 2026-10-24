"""FR-PLAN-02: debit AI text credits / voice minutes against the ledger."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

import logging

from app.core.config import settings
from app.models.plan import AICreditLedgerEntry, Plan, PlanCode, ShopSubscription
from app.models.shop import Shop

logger = logging.getLogger(__name__)


def _balance(db: Session, shop_id: uuid.UUID, kind: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
        .filter(AICreditLedgerEntry.shop_id == shop_id, AICreditLedgerEntry.kind == kind)
        .scalar()
    )
    return float(total or 0)


def ensure_monthly_grant(db: Session, shop_id: uuid.UUID) -> None:
    """Grant plan monthly credits once per calendar month if ledger is empty for the month."""
    shop = db.get(Shop, shop_id)
    if shop is None:
        return
    sub = db.query(ShopSubscription).filter(ShopSubscription.shop_id == shop_id).first()
    plan_code = sub.plan_code if sub else PlanCode.FREE
    try:
        plan_code = PlanCode(shop.plan_tier) if not sub else plan_code
    except ValueError:
        plan_code = PlanCode.FREE
    plan = db.query(Plan).filter(Plan.code == plan_code).first()
    text_grant = float(plan.monthly_ai_credits) if plan else 60.0
    voice_grant = float(plan.monthly_voice_minutes) if plan else 30.0

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    already = (
        db.query(AICreditLedgerEntry)
        .filter(
            AICreditLedgerEntry.shop_id == shop_id,
            AICreditLedgerEntry.reason == f"monthly_reset:{month_key}",
        )
        .first()
    )
    if already:
        return
    if text_grant:
        db.add(
            AICreditLedgerEntry(
                shop_id=shop_id,
                kind="text_credit",
                amount=text_grant,
                reason=f"monthly_reset:{month_key}",
            )
        )
    if voice_grant:
        db.add(
            AICreditLedgerEntry(
                shop_id=shop_id,
                kind="voice_minute",
                amount=voice_grant,
                reason=f"monthly_reset:{month_key}",
            )
        )
    db.flush()


def consume_text_credit(
    db: Session,
    shop_id: uuid.UUID,
    reason: str = "ai_reply",
    amount: float = 1.0,
    page_id: str | None = None,
) -> bool:
    if settings.environment == "development":
        return True
    ensure_monthly_grant(db, shop_id)
    if _balance(db, shop_id, "text_credit") < amount:
        logger.warning("Shop %s has exhausted AI text credits (required: %s)", shop_id, amount)
        return False
    db.add(
        AICreditLedgerEntry(
            shop_id=shop_id,
            kind="text_credit",
            amount=-abs(amount),
            reason=reason,
            page_id=page_id,
        )
    )
    db.flush()
    return True


def consume_voice_minutes(db: Session, shop_id: uuid.UUID, minutes: float = 1.0, reason: str = "call_minute") -> bool:
    ensure_monthly_grant(db, shop_id)
    if _balance(db, shop_id, "voice_minute") < minutes:
        return False
    db.add(
        AICreditLedgerEntry(
            shop_id=shop_id,
            kind="voice_minute",
            amount=-abs(minutes),
            reason=reason,
        )
    )
    db.flush()
    return True


def module_enabled(shop: Shop, module: str, default: bool = True) -> bool:
    toggles = shop.ai_module_toggles or {}
    return bool(toggles.get(module, default))
