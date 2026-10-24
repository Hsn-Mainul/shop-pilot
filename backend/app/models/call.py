import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class CallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    HANDED_OVER = "handed_over"
    COMPLETED = "completed"
    MISSED = "missed"
    VOICEMAIL = "voicemail"


class CallSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "call_sessions"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    direction: Mapped[CallDirection] = mapped_column(Enum(CallDirection))
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.RINGING)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    recording_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str | None] = mapped_column(String, nullable=True)
    dialect_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dialect_packs.id"), nullable=True
    )
    handled_by_ai: Mapped[bool] = mapped_column(default=True)
    handed_over_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team_members.id"), nullable=True
    )
