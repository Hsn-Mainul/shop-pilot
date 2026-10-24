import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class SupportRequestStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class SupportRequest(UUIDMixin, TimestampMixin, Base):
    """In-app support ticket (FR-SUP-01)."""

    __tablename__ = "support_requests"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[SupportRequestStatus] = mapped_column(Enum(SupportRequestStatus), default=SupportRequestStatus.OPEN)
