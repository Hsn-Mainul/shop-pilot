import uuid

from pydantic import BaseModel

from app.models.conversation import ConversationChannel, ConversationStatus, MessageDirection, MessageType


class MessageCreate(BaseModel):
    direction: MessageDirection = MessageDirection.OUTBOUND
    type: MessageType = MessageType.TEXT
    text: str | None = None
    audio_ref: str | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    direction: MessageDirection
    type: MessageType
    text: str | None
    audio_ref: str | None
    transcript_confidence: float | None
    detected_language: str | None
    sent_by_ai: bool
    delivery_status: str | None = None
    delivery_detail: str | None = None

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    channel: ConversationChannel
    status: ConversationStatus
    assigned_team_member_id: uuid.UUID | None
    page_id: str | None = None

    model_config = {"from_attributes": True}


class ConversationHandover(BaseModel):
    assigned_team_member_id: uuid.UUID
    summary_note: str | None = None


class ConversationCreate(BaseModel):
    customer_id: uuid.UUID
    channel: ConversationChannel = ConversationChannel.FACEBOOK
    initial_message: str | None = None
