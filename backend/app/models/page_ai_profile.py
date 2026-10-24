import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PageAIType(str, enum.Enum):
    POLITICAL_CAMPAIGN = "political_campaign"
    ECOMMERCE = "ecommerce"
    MEDIA = "media"
    NON_PROFIT = "non_profit"
    COMMUNITY = "community"
    SERVICES = "services"
    CREATOR = "creator"
    GENERAL = "general"


class PageAIProfile(UUIDMixin, TimestampMixin, Base):
    """Page-specific AI training, persona, and study profile for integrated social pages (FB, IG, etc.)."""

    __tablename__ = "page_ai_profiles"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    page_id: Mapped[str] = mapped_column(String(120), index=True)
    platform: Mapped[str] = mapped_column(String(50), default="facebook")
    page_name: Mapped[str] = mapped_column(String(255))
    page_category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    detected_type: Mapped[str] = mapped_column(String(50), default="general")

    # Meta Graph analysis details
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_study_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Page-specific AI Persona & Training
    ai_persona_name: Mapped[str] = mapped_column(String(150), default="AI Representative")
    ai_role_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(String(100), default="Inspiring & Civic")
    key_topics: Mapped[list] = mapped_column(JSONB, default=list)
    dos_and_donts: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Guardrails & Features
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    include_product_catalog: Mapped[bool] = mapped_column(Boolean, default=False)

    # Study metadata
    study_status: Mapped[str] = mapped_column(String(50), default="not_studied")
    last_studied_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
