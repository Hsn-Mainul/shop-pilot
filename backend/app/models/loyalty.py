import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class RewardStatus(str, enum.Enum):
    WAITING = "waiting"
    SENT = "sent"
    SET_ASIDE = "set_aside"


class LoyaltyReward(UUIDMixin, TimestampMixin, Base):
    """AI-drafted thank-you/reward on a milestone order, queued for approval (FR-CUST-03)."""

    __tablename__ = "loyalty_rewards"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    milestone_order_number: Mapped[int] = mapped_column(Integer)  # 2nd, 3rd, 5th, 10th order
    draft_message: Mapped[str] = mapped_column(Text)
    status: Mapped[RewardStatus] = mapped_column(Enum(RewardStatus), default=RewardStatus.WAITING)
