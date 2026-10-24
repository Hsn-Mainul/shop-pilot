import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class SavedReply(UUIDMixin, TimestampMixin, Base):
    """Shortcut-tagged, merge-variable reply template (FR-CHAT-03)."""

    __tablename__ = "saved_replies"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    shortcut: Mapped[str] = mapped_column(String(50))  # e.g. "/confirm"
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)  # may contain {{first_name}}, {{shop_name}}, ...
    language: Mapped[str] = mapped_column(String(10), default="en")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
