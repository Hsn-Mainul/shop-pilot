import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class WebhookEvent(UUIDMixin, TimestampMixin, Base):
    """Raw inbound event from a connected provider, queued for processing.

    The signature is verified at receipt time; the payload is stored as-is so
    the appropriate service (Conversation, Payment, Delivery, ...) can process
    it asynchronously without re-requesting it from the provider.
    """

    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(String(50), index=True)
    shop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
