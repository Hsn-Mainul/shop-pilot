import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.conversation import (
    Conversation,
    ConversationChannel,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageType,
)
from app.integrations.asr import ASRNotConfiguredError, transcribe_audio_file
from app.models.order import Order
from app.models.team_member import TeamMember, TeamRole
from app.models.customer import Customer
from app.schemas.conversation import (
    ConversationCreate,
    ConversationHandover,
    ConversationOut,
    MessageCreate,
    MessageOut,
)
from app.realtime.hub import hub
from app.services.automation_engine import trigger_event
from app.services.channel_outbound import deliver_outbound

router = APIRouter(prefix="/conversations", tags=["conversations"])

PRICE_REQUEST_KEYWORDS = ("price", "koto", "দাম", "কত")


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> ConversationOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.shop_id == current_user.shop_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    conversation = Conversation(
        shop_id=current_user.shop_id,
        customer_id=customer.id,
        channel=payload.channel,
        status=ConversationStatus.OPEN,
    )
    db.add(conversation)
    db.flush()
    if payload.initial_message:
        msg = Message(
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
            text=payload.initial_message,
        )
        db.add(msg)
        db.flush()
        deliver_outbound(db, conversation, payload.initial_message, message=msg)
    db.commit()
    db.refresh(conversation)
    hub.broadcast_sync(
        current_user.shop_id,
        "conversation.created",
        {"conversation_id": str(conversation.id)},
    )
    return conversation


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    status_filter: ConversationStatus | None = None,
    channel_filter: ConversationChannel | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    query = db.query(Conversation).filter(Conversation.shop_id == current_user.shop_id)
    if status_filter:
        query = query.filter(Conversation.status == status_filter)
    if channel_filter:
        query = query.filter(Conversation.channel == channel_filter)

    # Protect conversations based on page visibility marks & user-specific permissions
    if current_user.role != TeamRole.SUPER_ADMIN:
        from app.models.page_ai_profile import PageAIProfile
        from app.models.page_permission import PageUserPermission

        all_pids = [
            row[0]
            for row in db.query(PageAIProfile.page_id)
            .filter(PageAIProfile.shop_id == current_user.shop_id)
            .all()
        ]
        permitted_pids = set(
            row[0]
            for row in db.query(PageUserPermission.page_id)
            .filter(PageUserPermission.user_id == current_user.id, PageUserPermission.can_view.is_(True))
            .all()
        )
        invisible_pids = set(
            row[0]
            for row in db.query(PageAIProfile.page_id)
            .filter(PageAIProfile.shop_id == current_user.shop_id, PageAIProfile.is_visible.is_(False))
            .all()
        )

        forbidden_pids = [
            pid for pid in all_pids
            if pid in invisible_pids or pid not in permitted_pids
        ]
        if forbidden_pids:
            query = query.filter((Conversation.page_id.is_(None)) | (~Conversation.page_id.in_(forbidden_pids)))

    return query.order_by(Conversation.updated_at.desc()).all()


@router.get("/stats")
def inbox_stats(
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """FR-CHAT-07: aggregate inbox KPIs for the dashboard."""
    shop_id = current_user.shop_id

    waiting_count = (
        db.query(Conversation)
        .filter(Conversation.shop_id == shop_id, Conversation.status == ConversationStatus.OPEN)
        .count()
    )

    price_request_count = (
        db.query(Message)
        .join(Conversation)
        .filter(
            Conversation.shop_id == shop_id,
            Message.direction == MessageDirection.INBOUND,
        )
        .filter(or_(*[Message.text.ilike(f"%{kw}%") for kw in PRICE_REQUEST_KEYWORDS]))
        .count()
    )

    reply_gaps = (
        db.query(Message.conversation_id, Message.direction, Message.created_at)
        .join(Conversation)
        .filter(Conversation.shop_id == shop_id)
        .order_by(Message.conversation_id, Message.created_at)
        .all()
    )
    deltas: list[float] = []
    last_inbound: dict[uuid.UUID, datetime] = {}
    for conv_id, direction, created_at in reply_gaps:
        if direction == MessageDirection.INBOUND:
            last_inbound[conv_id] = created_at
        elif conv_id in last_inbound:
            deltas.append((created_at - last_inbound.pop(conv_id)).total_seconds())
    avg_reply_seconds = sum(deltas) / len(deltas) if deltas else None

    orders_from_comments = (
        db.query(Order).filter(Order.shop_id == shop_id, Order.source_channel == "comment").count()
    )

    return {
        "conversations_waiting_for_reply": waiting_count,
        "price_request_messages": price_request_count,
        "average_reply_time_seconds": avg_reply_seconds,
        "orders_from_comments": orders_from_comments,
    }


def _get_owned_conversation(conversation_id: uuid.UUID, current_user: TeamMember, db: Session) -> Conversation:
    conversation = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages))
        .filter(Conversation.id == conversation_id, Conversation.shop_id == current_user.shop_id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: uuid.UUID,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    conversation = _get_owned_conversation(conversation_id, current_user, db)
    return conversation.messages


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> MessageOut:
    conversation = _get_owned_conversation(conversation_id, current_user, db)
    message = Message(conversation_id=conversation.id, **payload.model_dump())
    db.add(message)
    db.flush()

    delivery = None
    if message.direction == MessageDirection.OUTBOUND and message.text:
        delivery = deliver_outbound(db, conversation, message.text, message=message)
        conversation.status = ConversationStatus.WAITING_ON_CUSTOMER
        db.add(conversation)

    db.commit()
    db.refresh(message)
    hub.broadcast_sync(
        current_user.shop_id,
        "message.created",
        {
            "conversation_id": str(conversation.id),
            "message_id": str(message.id),
            "channel_delivery": delivery,
        },
    )

    if message.direction == MessageDirection.INBOUND:
        trigger_event(
            db,
            conversation.shop_id,
            "message.received",
            {"conversation_id": conversation.id, "actor_id": current_user.id},
        )

    return message


@router.post("/{conversation_id}/messages/{message_id}/transcribe", response_model=MessageOut)
def transcribe_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    language_hint: str | None = None,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> MessageOut:
    """FR-CHAT-06/FR-VOICE-01: real transcription of a voice-note message.
    `audio_ref` is read as a local file path (see Document/Media Object
    Storage in the architecture doc for how this would be a real object-store
    URL in production)."""
    conversation = _get_owned_conversation(conversation_id, current_user, db)
    message = next((m for m in conversation.messages if m.id == message_id), None)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.type != MessageType.VOICE_NOTE or not message.audio_ref:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is not a voice note")

    try:
        text, confidence = transcribe_audio_file(message.audio_ref, language_hint=language_hint)
    except ASRNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found at audio_ref")

    message.text = text
    message.transcript_confidence = confidence
    message.detected_language = language_hint
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/{conversation_id}/handover", response_model=ConversationOut)
def handover_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationHandover,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> ConversationOut:
    conversation = _get_owned_conversation(conversation_id, current_user, db)
    conversation.assigned_team_member_id = payload.assigned_team_member_id
    conversation.status = ConversationStatus.HANDED_OVER
    if payload.summary_note:
        db.add(
            Message(
                conversation_id=conversation.id,
                direction=MessageDirection.OUTBOUND,
                text=f"[Handover summary] {payload.summary_note}",
                sent_by_ai=True,
            )
        )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation
