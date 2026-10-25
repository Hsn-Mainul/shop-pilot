import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ConversationChannel(str, enum.Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    TIKTOK = "tiktok"
    COMMENT = "comment"
    WEBHOOK = "webhook"


class ConversationStatus(str, enum.Enum):
    OPEN = "open"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    HANDED_OVER = "handed_over"
    CLOSED = "closed"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE_NOTE = "voice_note"
    SYSTEM = "system"


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    channel: Mapped[ConversationChannel] = mapped_column(Enum(ConversationChannel))
    status: Mapped[ConversationStatus] = mapped_column(Enum(ConversationStatus), default=ConversationStatus.OPEN)
    assigned_team_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team_members.id"), nullable=True
    )
    page_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection))
    type: Mapped[MessageType] = mapped_column(Enum(MessageType), default=MessageType.TEXT)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The provider's own message id (e.g. Meta's `message.mid`) — webhook providers
    # commonly redeliver the same event at-least-once, and customers sometimes
    # double-send the same attachment; this lets us recognize and skip an exact
    # repeat instead of running a full fresh AI reply (vision + LLM calls) for it.
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sent_by_ai: Mapped[bool] = mapped_column(default=False)
    # Channel delivery feedback for outbound replies (sent | failed | local | pending)
    delivery_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Text, not VARCHAR(250): a full Meta Graph API error body needs more room than
    # that to actually be diagnosable instead of cutting off mid-sentence.
    delivery_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
