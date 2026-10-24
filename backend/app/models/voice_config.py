import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class VoicePersona(UUIDMixin, TimestampMixin, Base):
    """AI voice persona choice + call-script training (FR-VPER-01/02)."""

    __tablename__ = "voice_personas"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), unique=True, index=True)
    voice_name: Mapped[str] = mapped_column(String(50), default="default_bn_female")
    tone: Mapped[str] = mapped_column(String(30), default="friendly")
    speaking_pace: Mapped[str] = mapped_column(String(20), default="normal")  # slow, normal, fast
    opening_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    must_confirm_before_order: Mapped[bool] = mapped_column(default=True)
    forbidden_topics: Mapped[list] = mapped_column(JSONB, default=list)


class CallRoutingRule(UUIDMixin, TimestampMixin, Base):
    """Business-hours / overflow / priority call routing (FR-CALL-11)."""

    __tablename__ = "call_routing_rules"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), unique=True, index=True)
    business_hours_start: Mapped[Time | None] = mapped_column(Time, nullable=True)
    business_hours_end: Mapped[Time | None] = mapped_column(Time, nullable=True)
    overflow_action: Mapped[str] = mapped_column(String(30), default="voicemail")  # voicemail, callback_request, ai_only
    prioritize_repeat_customers: Mapped[bool] = mapped_column(default=True)
    max_concurrent_human_lines: Mapped[int] = mapped_column(Integer, default=1)
