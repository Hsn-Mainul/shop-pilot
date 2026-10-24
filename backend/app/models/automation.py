import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AutomationKind(str, enum.Enum):
    RULE = "rule"
    WORKFLOW = "workflow"
    SCHEDULED_JOB = "scheduled_job"
    SENDING_RULE = "sending_rule"
    RECIPE = "recipe"


class AutomationRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "automation_rules"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    kind: Mapped[AutomationKind] = mapped_column(Enum(AutomationKind), default=AutomationKind.RULE)
    name: Mapped[str] = mapped_column(String(150))
    trigger: Mapped[str] = mapped_column(String(100))  # e.g. order.confirmed, stock.low, schedule.daily
    action: Mapped[str] = mapped_column(String(100))  # e.g. send_message, place_call, create_task
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class BulkCampaign(UUIDMixin, TimestampMixin, Base):
    """Bulk email / SMS / WhatsApp / voice-call campaigns (FR-CUST-06/07)."""

    __tablename__ = "bulk_campaigns"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # email, sms, whatsapp, voice
    segment: Mapped[str] = mapped_column(String(100))  # all, repeat_customers, region:<name>, custom_list
    message_template: Mapped[str] = mapped_column(String, default="")
    scheduled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, scheduled, sending, completed
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    opted_out_excluded_count: Mapped[int] = mapped_column(Integer, default=0)


class CustomerChannelOptOut(UUIDMixin, TimestampMixin, Base):
    """Per-channel opt-out enforcement (FR-CUST-08)."""

    __tablename__ = "customer_channel_opt_outs"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # email, sms, whatsapp, voice
