import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PlanCode(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class Plan(UUIDMixin, TimestampMixin, Base):
    """Reference catalogue of subscription tiers (FR-PLAN-01) with System Admin usage rates."""

    __tablename__ = "plans"

    code: Mapped[PlanCode] = mapped_column(Enum(PlanCode), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    monthly_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    channel_limit: Mapped[int] = mapped_column(Integer, default=1)
    team_seat_limit: Mapped[int] = mapped_column(Integer, default=2)
    monthly_ai_credits: Mapped[int] = mapped_column(Integer, default=60)
    monthly_voice_minutes: Mapped[int] = mapped_column(Integer, default=0)
    extra_credit_rate_per_k: Mapped[float] = mapped_column(Numeric(12, 2), default=10.0)
    extra_voice_rate_per_min: Mapped[float] = mapped_column(Numeric(12, 2), default=0.20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ShopSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shop_subscriptions"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), unique=True, index=True)
    plan_code: Mapped[PlanCode] = mapped_column(Enum(PlanCode), default=PlanCode.FREE)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, trialing, past_due, cancelled
    renews_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AICreditLedgerEntry(UUIDMixin, TimestampMixin, Base):
    """Metered AI usage, text credits and voice minutes tracked separately (FR-PLAN-02)."""

    __tablename__ = "ai_credit_ledger_entries"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # text_credit, voice_minute, purchased_pack
    amount: Mapped[float] = mapped_column(Numeric(12, 2))  # negative = consumed, positive = granted/purchased
    reason: Mapped[str] = mapped_column(String(100))  # e.g. ai_reply, call_minute, monthly_reset, pack_purchase
    page_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
