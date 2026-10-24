"""Inbound channel → Customer + Conversation + Message (unified inbox)."""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationChannel,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageType,
)
from app.models.customer import Customer
from app.models.shop import Shop
from app.realtime.hub import hub
from app.services.automation_engine import trigger_event

logger = logging.getLogger(__name__)

SPAM_PATTERNS = re.compile(
    r"(free\s*money|click\s*here|bit\.ly|crypto\s*giveaway|earn\s*\$|whatsapp\s*\+?\d{8,})",
    re.I,
)
PHONE_IN_TEXT = re.compile(r"(?:\+?88)?01[3-9]\d{8}|\+?\d{10,15}")


_CHANNEL_PREFIX = {
    ConversationChannel.FACEBOOK: "fb",
    ConversationChannel.INSTAGRAM: "ig",
    ConversationChannel.WHATSAPP: "wa",
    ConversationChannel.TELEGRAM: "tg",
    ConversationChannel.COMMENT: "cmt",
    ConversationChannel.WEBHOOK: "wh",
}


def _channel_identity(channel: ConversationChannel, external_id: str) -> str:
    prefix = _CHANNEL_PREFIX.get(channel, "ch")
    return f"{prefix}:{external_id}"[:80]


def get_or_create_customer(
    db: Session,
    shop_id: uuid.UUID,
    *,
    external_id: str,
    channel: ConversationChannel,
    name: str | None = None,
) -> Customer:
    identity = _channel_identity(channel, external_id)
    customer = (
        db.query(Customer)
        .filter(Customer.shop_id == shop_id, Customer.phone == identity)
        .first()
    )
    if customer:
        if name and not customer.name:
            customer.name = name
            db.add(customer)
        return customer
    customer = Customer(
        shop_id=shop_id,
        name=name or external_id[:40],
        phone=identity,
        source=channel.value,
    )
    db.add(customer)
    db.flush()
    return customer


def get_or_create_conversation(
    db: Session,
    shop_id: uuid.UUID,
    customer: Customer,
    channel: ConversationChannel,
) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.shop_id == shop_id,
            Conversation.customer_id == customer.id,
            Conversation.channel == channel,
            Conversation.status.in_(
                [ConversationStatus.OPEN, ConversationStatus.WAITING_ON_CUSTOMER, ConversationStatus.HANDED_OVER]
            ),
        )
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    if conv:
        return conv
    conv = Conversation(
        shop_id=shop_id,
        customer_id=customer.id,
        channel=channel,
        status=ConversationStatus.OPEN,
    )
    db.add(conv)
    db.flush()
    return conv


def ingest_inbound_message(
    db: Session,
    shop_id: uuid.UUID,
    *,
    channel: ConversationChannel,
    external_user_id: str,
    text: str | None,
    name: str | None = None,
    msg_type: MessageType = MessageType.TEXT,
    media_ref: str | None = None,
    actor_id: uuid.UUID | None = None,
    comment_id: str | None = None,
    page_id: str | None = None,
) -> Message | None:
    shop = db.get(Shop, shop_id)
    if shop is None:
        return None

    # Comment moderation (FR-CHAT / shop toggles)
    if channel == ConversationChannel.COMMENT and text:
        if shop.auto_hide_spam_comments and SPAM_PATTERNS.search(text):
            logger.info("auto-hid spam comment for shop %s", shop_id)
            if comment_id:
                _try_hide_meta_comment(db, shop_id, comment_id)
            return None
        if shop.auto_hide_phone_numbers_in_comments and PHONE_IN_TEXT.search(text):
            text = PHONE_IN_TEXT.sub("[phone hidden]", text)

    customer = get_or_create_customer(
        db, shop_id, external_id=external_user_id, channel=channel, name=name
    )
    if comment_id:
        customer.email = f"comment:{comment_id}"[:255]
        db.add(customer)
    elif page_id:
        customer.email = f"page:{page_id}"[:255]
        db.add(customer)
    if customer.is_blocked:
        return None

    conversation = get_or_create_conversation(db, shop_id, customer, channel)
    if page_id:
        conversation.page_id = str(page_id)
    conversation.status = ConversationStatus.OPEN
    db.add(conversation)

    message = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND,
        type=msg_type,
        text=text,
        audio_ref=media_ref,
    )
    db.add(message)
    db.flush()

    hub.broadcast_sync(
        shop_id,
        "message.created",
        {"conversation_id": str(conversation.id), "message_id": str(message.id)},
    )
    trigger_event(
        db,
        shop_id,
        "message.received",
        {"conversation_id": conversation.id, "actor_id": actor_id or customer.id},
    )

    _maybe_ai_auto_reply(db, shop, conversation, channel, text, comment_id=comment_id, page_id=page_id)
    return message


def _try_hide_meta_comment(db: Session, shop_id: uuid.UUID, comment_id: str) -> None:
    try:
        from app.integrations.meta_graph import hide_comment
        from app.models.integration import Integration, IntegrationStatus

        for provider in ("facebook", "instagram"):
            integ = (
                db.query(Integration)
                .filter(
                    Integration.shop_id == shop_id,
                    Integration.provider == provider,
                    Integration.status == IntegrationStatus.CONNECTED,
                )
                .first()
            )
            token = (integ.config or {}).get("page_access_token") if integ else None
            if token:
                hide_comment(comment_id, token, hide=True)
                return
    except Exception:
        logger.debug("Meta hide_comment failed", exc_info=True)


def _recent_conversation_history(db: Session, conversation_id: uuid.UUID, limit: int = 10) -> str:
    """Prior turns of this conversation (most recent `limit`, oldest first),
    excluding the newest inbound message (passed separately as the current
    message) — so the AI doesn't re-ask for details the customer already gave
    earlier in the same chat."""
    recent = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit + 1)
        .all()
    )
    prior = list(reversed(recent))[:-1] if len(recent) > 1 else []
    lines = []
    for m in prior:
        if not m.text:
            continue
        speaker = "Customer" if m.direction == MessageDirection.INBOUND else "Shop"
        lines.append(f"{speaker}: {m.text.strip()}")
    return "\n".join(lines)


def _maybe_ai_auto_reply(
    db: Session,
    shop: Shop,
    conversation: Conversation,
    channel: ConversationChannel,
    text: str | None,
    *,
    comment_id: str | None = None,
    page_id: str | None = None,
) -> None:
    """Autopilot for comments (ai_auto_reply_comments) and DMs (ai_module_toggles.conversations)."""
    if not text:
        return
    toggles = shop.ai_module_toggles or {}
    is_comment = channel == ConversationChannel.COMMENT
    is_dm = channel in (
        ConversationChannel.FACEBOOK,
        ConversationChannel.INSTAGRAM,
        ConversationChannel.WHATSAPP,
        ConversationChannel.TELEGRAM,
    )
    if is_comment:
        if not (shop.ai_auto_reply_comments and toggles.get("comments", True)):
            return
        reason = "comment_auto_reply"
    elif is_dm:
        if not toggles.get("conversations", False):
            # Opt-in: conversations toggle must be explicitly on for DM autopilot
            return
        if conversation.status == ConversationStatus.HANDED_OVER:
            return
        reason = "dm_auto_reply"
    else:
        return

    try:
        from app.api.v1.endpoints.ai import _answer_from_shop_knowledge
        from app.models.page_ai_profile import PageAIProfile
        from app.services.ai_credits import consume_text_credit
        from app.services.channel_outbound import deliver_outbound

        page_profile: PageAIProfile | None = None
        if page_id:
            page_profile = (
                db.query(PageAIProfile)
                .filter(PageAIProfile.shop_id == shop.id, PageAIProfile.page_id == page_id)
                .first()
            )
            # If AI auto-reply is disabled for this specific page, do not send reply
            if page_profile and not page_profile.auto_reply_enabled:
                return

        if not consume_text_credit(db, shop.id, reason=reason, page_id=page_id):
            return

        history = _recent_conversation_history(db, conversation.id)
        reply_text = _answer_from_shop_knowledge(db, shop, text, page_id=page_id, history=history)
        signoff_name = page_profile.page_name if (page_profile and page_profile.page_name) else shop.name
        if signoff_name.lower() not in reply_text.lower():
            reply_text = f"{reply_text}\n\n— {signoff_name}"

        if is_dm:
            try:
                from app.services.chat_order_service import try_confirm_order_from_chat

                order_message = try_confirm_order_from_chat(db, shop, conversation)
                if order_message:
                    reply_text = f"{reply_text}\n\n{order_message}"
            except Exception:
                logger.warning("Chat-to-order confirmation check failed", exc_info=True)

        outbound = Message(
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
            text=reply_text,
            sent_by_ai=True,
        )
        db.add(outbound)
        db.flush()
        delivery = deliver_outbound(db, conversation, reply_text, comment_id=comment_id, message=outbound, page_id=page_id)
        conversation.status = ConversationStatus.WAITING_ON_CUSTOMER
        db.add(conversation)
        db.commit()
        hub.broadcast_sync(
            shop.id,
            "message.created",
            {"conversation_id": str(conversation.id), "message_id": str(outbound.id), "channel_delivery": delivery},
        )
    except Exception as exc:
        logger.warning("AI auto-reply failed: %s", exc, exc_info=True)


def parse_meta_messaging_payload(payload: dict) -> list[dict]:
    """Normalize Meta Messenger / Instagram / WhatsApp Cloud webhook entries."""
    out: list[dict] = []
    for entry in payload.get("entry") or []:
        # Messaging (Messenger / IG DM)
        for event in entry.get("messaging") or []:
            sender = (event.get("sender") or {}).get("id")
            recipient = (event.get("recipient") or {}).get("id") or entry.get("id")
            message = event.get("message") or {}
            if not sender or message.get("is_echo"):
                continue
            text = message.get("text")
            attachments = message.get("attachments") or []
            media = None
            msg_type = "text"
            if attachments:
                att = attachments[0]
                media = (att.get("payload") or {}).get("url")
                kind = att.get("type") or "image"
                msg_type = "voice_note" if kind in ("audio", "voice") else "image" if kind == "image" else "text"
            out.append(
                {
                    "channel": "instagram" if "instagram" in str(payload.get("object", "")).lower() else "facebook",
                    "external_user_id": sender,
                    "text": text,
                    "media_ref": media,
                    "msg_type": msg_type,
                    "name": None,
                    "page_id": str(recipient) if recipient else None,
                }
            )
        # Feed comments
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            if change.get("field") not in ("feed", "comments", "mention"):
                # WhatsApp Cloud style
                if "messages" in value:
                    for m in value.get("messages") or []:
                        out.append(
                            {
                                "channel": "whatsapp",
                                "external_user_id": m.get("from") or "",
                                "text": (m.get("text") or {}).get("body"),
                                "media_ref": None,
                                "msg_type": "text",
                                "name": None,
                            }
                        )
                continue
            comment_id = value.get("comment_id") or value.get("id")
            from_id = (value.get("from") or {}).get("id") or value.get("sender_id")
            if not from_id:
                continue
            out.append(
                {
                    "channel": "comment",
                    "external_user_id": str(from_id),
                    "text": value.get("message") or value.get("text"),
                    "media_ref": None,
                    "msg_type": "text",
                    "name": (value.get("from") or {}).get("name"),
                    "comment_id": str(comment_id) if comment_id else None,
                }
            )
    return out


def resolve_shop_id_for_meta(db: Session, payload: dict, fallback: uuid.UUID | None) -> uuid.UUID | None:
    """Match webhook entry.page_id / object id to a connected Integration."""
    if fallback is not None:
        return fallback
    from app.models.integration import Integration, IntegrationStatus

    page_ids: set[str] = set()
    for entry in payload.get("entry") or []:
        if entry.get("id"):
            page_ids.add(str(entry["id"]))
        for event in entry.get("messaging") or []:
            recipient = (event.get("recipient") or {}).get("id")
            if recipient:
                page_ids.add(str(recipient))
    if not page_ids:
        return None
    integrations = (
        db.query(Integration)
        .filter(
            Integration.provider.in_(["facebook", "instagram", "whatsapp"]),
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .all()
    )
    for integ in integrations:
        cfg = integ.config or {}
        if str(cfg.get("page_id") or "") in page_ids or str(cfg.get("ig_user_id") or "") in page_ids:
            return integ.shop_id
        for p in cfg.get("pages") or []:
            if str(p.get("id") or "") in page_ids:
                return integ.shop_id
        for a in cfg.get("accounts") or []:
            if str(a.get("id") or "") in page_ids or str(a.get("linked_page_id") or "") in page_ids:
                return integ.shop_id
    return None


def apply_meta_inbound(db: Session, shop_id: uuid.UUID, payload: dict) -> int:
    """Ingest all messaging/comment events from a Meta-style payload. Returns count."""
    type_map = {
        "text": MessageType.TEXT,
        "image": MessageType.IMAGE,
        "voice_note": MessageType.VOICE_NOTE,
    }
    channel_map = {
        "facebook": ConversationChannel.FACEBOOK,
        "instagram": ConversationChannel.INSTAGRAM,
        "whatsapp": ConversationChannel.WHATSAPP,
        "telegram": ConversationChannel.TELEGRAM,
        "comment": ConversationChannel.COMMENT,
    }
    count = 0
    for item in parse_meta_messaging_payload(payload):
        ch = channel_map.get(item["channel"])
        if not ch or not item.get("external_user_id"):
            continue
        msg = ingest_inbound_message(
            db,
            shop_id,
            channel=ch,
            external_user_id=item["external_user_id"],
            text=item.get("text"),
            name=item.get("name"),
            msg_type=type_map.get(item.get("msg_type") or "text", MessageType.TEXT),
            media_ref=item.get("media_ref"),
            comment_id=item.get("comment_id"),
            page_id=item.get("page_id"),
        )
        if msg:
            count += 1
    return count
