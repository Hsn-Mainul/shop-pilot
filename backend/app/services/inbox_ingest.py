"""Inbound channel → Customer + Conversation + Message (unified inbox)."""
from __future__ import annotations

import logging
import os
import re
import tempfile
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
from app.models.product import Product
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


def _transcribe_voice_note(media_ref: str) -> tuple[str | None, float | None]:
    """Transcribe an inbound voice note to text so it can be stored (visible in
    the inbox like a normal message) and fed into the same catalog-search /
    AI-reply pipeline a typed message would use. Returns (None, None) if ASR
    isn't configured or transcription fails — the caller then falls back to
    just storing the voice note without a reply, same as before this existed.
    """
    from app.integrations.asr import ASRNotConfiguredError, transcribe_audio_file
    from app.services.media_resolver import resolve_photo_bytes

    try:
        resolved = resolve_photo_bytes(media_ref)
        if not resolved:
            return None, None
        audio_bytes, filename = resolved
        suffix = os.path.splitext(filename)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            text, confidence = transcribe_audio_file(tmp_path)
            return (text or None), confidence
        finally:
            os.unlink(tmp_path)
    except ASRNotConfiguredError:
        logger.info("Voice note received but ASR is not configured (ASR_API_KEY) — skipping transcription")
        return None, None
    except Exception:
        logger.warning("Voice note transcription failed", exc_info=True)
        return None, None


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
    external_message_id: str | None = None,
) -> Message | None:
    shop = db.get(Shop, shop_id)
    if shop is None:
        return None

    if external_message_id:
        # Webhook providers deliver at-least-once, and customers sometimes double-send
        # the same attachment — either way, an exact repeat of a message we've already
        # ingested should not trigger a whole new (costly, and visibly repetitive) AI
        # reply cycle.
        already = (
            db.query(Message).filter(Message.external_message_id == external_message_id).first()
        )
        if already:
            logger.info("Skipping duplicate inbound message %s", external_message_id)
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

    transcript_confidence = None
    if msg_type == MessageType.VOICE_NOTE and not text and media_ref:
        transcript, transcript_confidence = _transcribe_voice_note(media_ref)
        if transcript:
            text = transcript

    message = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND,
        type=msg_type,
        text=text,
        audio_ref=media_ref,
        external_message_id=external_message_id,
        transcript_confidence=transcript_confidence,
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

    _maybe_ai_auto_reply(
        db,
        shop,
        conversation,
        channel,
        text,
        comment_id=comment_id,
        page_id=page_id,
        msg_type=msg_type,
        media_ref=media_ref,
    )
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


_PHOTO_REQUEST_INTENT = re.compile(
    r"(?:photo|picture|\bpic\b|image|"
    r"ছবি|chobi|dekhao|দেখাও|দেখান|"  # Bangla / Banglish
    r"फोटो|तस्वीर|दिखा|दिखाओ|दिखाना|दिखाइए|"  # Hindi
    r"تصویر|فوٹو|دکھاؤ|دکھائیں)",  # Urdu
    re.I,
)


def _find_requested_product_photo(
    db: Session, shop: Shop, text: str, page_id: str | None
) -> tuple[str, str] | None:
    """If the customer is asking to *see* a photo, find the best-matching
    catalog product and return (product_name, photo_url) — or None if the
    message isn't a photo request, or no matching product has a photo."""
    if not _PHOTO_REQUEST_INTENT.search(text):
        return None

    from app.services.rag_service import search_knowledge_and_catalog

    res = search_knowledge_and_catalog(
        db, shop.id, text, top_k_knowledge=0, top_k_products=1, page_id=page_id
    )
    products = res.get("products") or []
    if not products:
        return None
    product = db.get(Product, products[0]["id"])
    if product is None:
        return None
    if product.photo_url:
        return (product.name, product.photo_url)

    # The single best-matching product has no saved photo — fall back to a live
    # search of the connected page's own actual posts for THIS product, instead
    # of substituting some other, unrelated product's photo or just apologizing.
    # Only runs for a DM scoped to a specific connected page (need real credentials).
    if not page_id:
        return None
    try:
        from app.services.channel_outbound import meta_page_credentials
        from app.integrations.meta_graph import fetch_page_posts_with_photos

        creds = meta_page_credentials(db, shop.id, page_id=page_id)
        if creds is None:
            return None
        active_page_id, token = creds
        posts = fetch_page_posts_with_photos(active_page_id, token)
        found = _pick_matching_post(product.name, posts)
        if not found:
            return None
        # Cache it so the next request for this product is instant and needs no live call.
        product.photo_url = found["photo_url"]
        if found.get("permalink_url") and not product.post_link:
            product.post_link = found["permalink_url"]
        db.add(product)
        db.flush()
        return (product.name, found["photo_url"])
    except Exception:
        logger.warning("Live page-photo search failed", exc_info=True)
        return None


def _pick_matching_post(product_name: str, posts: list[dict]) -> dict | None:
    """Pick the post (if any) whose caption actually refers to `product_name`,
    using the LLM's language understanding rather than literal keyword
    matching — the page's own posts are often in Bangla ("টি-শার্ট এভেইলএবল")
    while catalog product names are typically typed in English ("T-Shirt"),
    so a plain substring/keyword match would never bridge the two scripts.
    """
    if not posts:
        return None

    from app.integrations.llm import LLMNotConfiguredError, chat_completion

    numbered = "\n".join(f"{i + 1}. {p['message'][:200] or '(no caption)'}" for i, p in enumerate(posts))
    prompt = (
        f"Product: \"{product_name}\"\n\nNumbered Facebook posts (any language):\n{numbered}\n\n"
        f"Which numbered post, if any, is actually about this product? Reply with ONLY the number, "
        f"or 0 if none of them are about it. No other text."
    )
    try:
        raw = chat_completion(
            "You match a product name to the right social media post, across languages.", prompt, max_tokens=10
        )
    except LLMNotConfiguredError:
        return None
    except Exception:
        logger.warning("Post-matching LLM call failed", exc_info=True)
        return None

    match = re.search(r"\d+", raw)
    if not match:
        return None
    idx = int(match.group())
    if idx < 1 or idx > len(posts):
        return None
    return posts[idx - 1]


def _effective_query_for_photo(media_ref: str) -> str | None:
    """Turn an inbound photo-only message into a text query the catalog search
    can use — describe the photo (what moondream is reliable at), then search
    the catalog for something matching that description, the same way a typed
    product search would."""
    try:
        from app.integrations.llm import describe_photo
        from app.services.media_resolver import resolve_photo_bytes

        resolved = resolve_photo_bytes(media_ref)
        if not resolved:
            return None
        image_bytes, _ = resolved
        description = describe_photo(image_bytes)
        if not description:
            return None
        return (
            f"The customer sent a photo instead of typing. What the photo shows: {description}. "
            f"Find the closest matching product(s) in the catalog and tell the customer about them "
            f"(name, price, availability). If nothing matches, say so and ask what they're looking for."
        )
    except Exception:
        logger.warning("Photo-based product search failed", exc_info=True)
        return None


_SHOW_ALL_INTENT = re.compile(r"\ball\b|সব|shob|সকল|every", re.I)
MAX_SHOW_ALL_PHOTOS = 10


def _find_all_category_photos(
    db: Session, shop: Shop, text: str, page_id: str | None, limit: int = MAX_SHOW_ALL_PHOTOS
) -> list[tuple[str, str]] | None:
    """If the customer is asking to see ALL photos/products (not one specific
    item), return up to `limit` products — one per distinct category — that
    already have a saved photo. Returns None if this isn't a "show all"
    request, so the caller falls through to the single-product photo lookup.
    """
    if not (_PHOTO_REQUEST_INTENT.search(text) and _SHOW_ALL_INTENT.search(text)):
        return None

    query = db.query(Product).filter(
        Product.shop_id == shop.id, Product.kind == "product", Product.photo_url.isnot(None)
    )
    if page_id:
        query = query.filter((Product.page_id == page_id) | (Product.page_id.is_(None)))
    products = query.order_by(Product.category, Product.created_at.desc()).all()

    seen_categories: set[str] = set()
    result: list[tuple[str, str]] = []
    for p in products:
        category = p.category or "uncategorized"
        if category in seen_categories:
            continue
        seen_categories.add(category)
        result.append((p.name, p.photo_url))
        if len(result) >= limit:
            break
    return result or None


def _maybe_ai_auto_reply(
    db: Session,
    shop: Shop,
    conversation: Conversation,
    channel: ConversationChannel,
    text: str | None,
    *,
    comment_id: str | None = None,
    page_id: str | None = None,
    msg_type: MessageType = MessageType.TEXT,
    media_ref: str | None = None,
) -> None:
    """Autopilot for comments (ai_auto_reply_comments) and DMs (ai_module_toggles.conversations)."""
    effective_text = text
    if not effective_text and msg_type == MessageType.IMAGE and media_ref:
        effective_text = _effective_query_for_photo(media_ref)
    if not effective_text:
        return
    text = effective_text
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

        # Short-circuit: if this is a tracking query, answer directly without
        # consuming a credit or hitting the LLM — the data lives in the DB.
        if is_dm:
            try:
                from app.services.chat_order_service import try_track_order_from_chat

                tracking_reply = try_track_order_from_chat(
                    db, shop, text, conversation.customer_id
                )
                if tracking_reply:
                    outbound = Message(
                        conversation_id=conversation.id,
                        direction=MessageDirection.OUTBOUND,
                        text=tracking_reply,
                        sent_by_ai=True,
                    )
                    db.add(outbound)
                    db.flush()
                    deliver_outbound(
                        db, conversation, tracking_reply, comment_id=comment_id, message=outbound, page_id=page_id
                    )
                    conversation.status = ConversationStatus.WAITING_ON_CUSTOMER
                    db.add(conversation)
                    db.commit()
                    hub.broadcast_sync(
                        shop.id,
                        "message.created",
                        {"conversation_id": str(conversation.id), "message_id": str(outbound.id)},
                    )
                    return
            except Exception:
                logger.warning("Order tracking lookup failed", exc_info=True)

        # Short-circuit: "show me all photos" sends up to MAX_SHOW_ALL_PHOTOS actual
        # images (one per distinct category), instead of the single-product photo flow.
        if is_dm:
            try:
                from app.services.channel_outbound import deliver_outbound_image

                all_photos = _find_all_category_photos(db, shop, text, page_id)
                if all_photos:
                    if not consume_text_credit(db, shop.id, reason=reason, page_id=page_id):
                        return
                    sent_names = []
                    for name, photo_url in all_photos:
                        result = deliver_outbound_image(db, conversation, photo_url, page_id=page_id)
                        if result.get("delivered"):
                            sent_names.append(name)
                    if len(all_photos) >= MAX_SHOW_ALL_PHOTOS:
                        summary = (
                            f"Here are {len(sent_names)} of our categories — we have even more, just ask about "
                            f"a specific item for more options: {', '.join(sent_names)}"
                        )
                    else:
                        summary = f"Here's what we have photos for: {', '.join(sent_names)}"
                    outbound = Message(
                        conversation_id=conversation.id,
                        direction=MessageDirection.OUTBOUND,
                        text=summary,
                        sent_by_ai=True,
                    )
                    db.add(outbound)
                    db.flush()
                    deliver_outbound(db, conversation, summary, comment_id=comment_id, message=outbound, page_id=page_id)
                    conversation.status = ConversationStatus.WAITING_ON_CUSTOMER
                    db.add(conversation)
                    db.commit()
                    hub.broadcast_sync(
                        shop.id,
                        "message.created",
                        {"conversation_id": str(conversation.id), "message_id": str(outbound.id)},
                    )
                    return
            except Exception:
                logger.warning("Show-all-photos flow failed", exc_info=True)

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

        # The AI's own reply text never claims to send a photo (see the system prompt) — only
        # this deterministic step actually attempts it and says what really happened, the same
        # way order confirmation works. That avoids the bot confidently claiming "I'm sending
        # a photo" and then nothing ever arriving if the real send fails.
        photo_sent = False
        if is_dm:
            try:
                from app.services.channel_outbound import deliver_outbound_image

                found = _find_requested_product_photo(db, shop, text, page_id)
                if found:
                    product_name, photo_url = found
                    photo_message = Message(
                        conversation_id=conversation.id,
                        direction=MessageDirection.OUTBOUND,
                        type=MessageType.IMAGE,
                        audio_ref=photo_url,
                        sent_by_ai=True,
                    )
                    db.add(photo_message)
                    db.flush()
                    photo_result = deliver_outbound_image(
                        db, conversation, photo_url, message=photo_message, page_id=page_id
                    )
                    if photo_result.get("delivered"):
                        photo_sent = True
                        reply_text = f"{reply_text}\n\n📷 ({product_name} photo sent above)"
                    else:
                        logger.warning(
                            "Photo attachment delivery failed for conversation %s: %s",
                            conversation.id,
                            photo_result.get("reason"),
                        )
                        reply_text = (
                            f"{reply_text}\n\n(I couldn't send the photo automatically just now — "
                            f"our team will follow up with it shortly.)"
                        )
            except Exception:
                logger.warning("Photo attachment send failed", exc_info=True)

        outbound = Message(
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
            text=reply_text,
            sent_by_ai=True,
        )
        db.add(outbound)
        db.flush()
        delivery = deliver_outbound(db, conversation, reply_text, comment_id=comment_id, message=outbound, page_id=page_id)
        if photo_sent:
            delivery["photo_sent"] = True
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
                    # Meta's own message id — webhooks are delivered at-least-once, so this
                    # is what lets us recognize and skip an exact redelivered duplicate.
                    "external_message_id": message.get("mid"),
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
                                # So per-page/number cost analysis can attribute this usage
                                # instead of it landing in the unattributed bucket.
                                "page_id": str(entry.get("id")) if entry.get("id") else None,
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
                    # The page this comment was posted on — without this, every comment-driven
                    # credit debit landed in the "unattributed" bucket in per-page cost analysis.
                    "page_id": str(entry.get("id")) if entry.get("id") else None,
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
            external_message_id=item.get("external_message_id"),
        )
        if msg:
            count += 1
    return count
