"""Send outbound inbox replies to the connected channel (Meta / Twilio / Telegram)."""
from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.integrations.messaging import MessagingNotConfiguredError, send_whatsapp
from app.integrations.meta_graph import (
    MetaNotConfiguredError,
    reply_to_comment,
    send_messenger_image,
    send_messenger_product_carousel,
    send_messenger_text,
)
from app.models.conversation import Conversation, ConversationChannel, Message
from app.models.customer import Customer
from app.models.integration import Integration, IntegrationStatus
from app.services.media_resolver import absolute_url as media_absolute_url

logger = logging.getLogger(__name__)


def _external_id_from_customer(customer: Customer | None, channel: ConversationChannel) -> str | None:
    if customer is None or not customer.phone:
        return None
    phone = customer.phone
    for prefix in ("fb:", "ig:", "wa:", "tg:", "cmt:", "wh:", "ch:"):
        if phone.startswith(prefix):
            return phone[len(prefix) :]
    if channel in (ConversationChannel.WHATSAPP, ConversationChannel.TELEGRAM):
        return phone
    return None


def meta_page_credentials(db: Session, shop_id: uuid.UUID, page_id: str | None = None) -> tuple[str, str] | None:
    """Resolve the active page ID + access token for a given page_id.

    Provider priority: facebook → instagram → whatsapp.
    When page_id is provided, ONLY return credentials whose resolved id
    actually matches — never return a different page's token just because it
    was the first integration found. Falls back to any connected credentials
    only when page_id is None (generic / no-page-context sends).
    """
    for provider in ("facebook", "instagram", "whatsapp"):
        integration = (
            db.query(Integration)
            .filter(
                Integration.shop_id == shop_id,
                Integration.provider == provider,
                Integration.status == IntegrationStatus.CONNECTED,
            )
            .first()
        )
        if integration:
            cfg = integration.config or {}
            # 1. Multi-page list
            for p in cfg.get("pages") or []:
                if page_id and str(p.get("id")) == str(page_id) and p.get("access_token"):
                    return str(p["id"]), str(p["access_token"])
                if not page_id and p.get("id") and p.get("access_token"):
                    return str(p["id"]), str(p["access_token"])
            # 2. Multi-account Instagram list
            for a in cfg.get("accounts") or []:
                if page_id and str(a.get("id")) == str(page_id) and a.get("page_access_token"):
                    return str(a["id"]), str(a["page_access_token"])
                if not page_id and a.get("id") and a.get("page_access_token"):
                    return str(a["id"]), str(a["page_access_token"])
            # 3. Top-level single page — ONLY match if the id actually equals the
            # requested page_id; never return a mismatched page's token.
            pid = cfg.get("page_id") or cfg.get("ig_user_id") or cfg.get("phone_number_id") or ""
            token = cfg.get("page_access_token")
            if pid and token:
                if not page_id or str(pid) == str(page_id):
                    return str(pid), str(token)
    return None


def _integration_config(db: Session, shop_id: uuid.UUID, provider: str) -> dict:
    integration = (
        db.query(Integration)
        .filter(
            Integration.shop_id == shop_id,
            Integration.provider == provider,
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .first()
    )
    return (integration.config if integration else {}) or {}


def apply_delivery_to_message(message: Message | None, result: dict) -> dict:
    """Persist delivery outcome on the Message row when provided."""
    if message is not None:
        if result.get("delivered"):
            message.delivery_status = "sent"
            detail = result.get("via") or result.get("provider_message_id") or "ok"
            message.delivery_detail = str(detail)
        else:
            message.delivery_status = "failed" if result.get("reason") != "empty" else "local"
            message.delivery_detail = str(result.get("reason") or "unknown")
    return result


def deliver_outbound(
    db: Session,
    conversation: Conversation,
    text: str,
    *,
    comment_id: str | None = None,
    message: Message | None = None,
    page_id: str | None = None,
) -> dict:
    """Best-effort channel delivery. Always returns a status dict; never raises for stub misses."""
    if not text:
        return apply_delivery_to_message(message, {"delivered": False, "reason": "empty"})

    customer = db.get(Customer, conversation.customer_id)
    recipient = _external_id_from_customer(customer, conversation.channel)
    channel = conversation.channel

    if channel in (
        ConversationChannel.FACEBOOK,
        ConversationChannel.INSTAGRAM,
        ConversationChannel.COMMENT,
    ):
        resolved_page_id = page_id
        if not resolved_page_id and customer and customer.email and customer.email.startswith("page:"):
            resolved_page_id = customer.email.split(":", 1)[1]

        creds = meta_page_credentials(db, conversation.shop_id, page_id=resolved_page_id)
        if creds is None and resolved_page_id:
            # Fallback to default page if specific page_id not found
            creds = meta_page_credentials(db, conversation.shop_id, page_id=None)
        if creds is None:
            return apply_delivery_to_message(message, {"delivered": False, "reason": "meta_not_connected"})
        active_page_id, token = creds
        try:
            if channel == ConversationChannel.COMMENT:
                cid = comment_id
                if not cid and customer and customer.email and customer.email.startswith("comment:"):
                    cid = customer.email.split(":", 1)[1]
                if cid:
                    mid = reply_to_comment(cid, token, text)
                    return apply_delivery_to_message(
                        message, {"delivered": True, "provider_message_id": mid, "via": "comment_reply"}
                    )
            if recipient:
                mid = send_messenger_text(active_page_id, token, recipient, text)
                return apply_delivery_to_message(
                    message, {"delivered": True, "provider_message_id": mid, "via": "messenger"}
                )
            return apply_delivery_to_message(message, {"delivered": False, "reason": "no_recipient"})
        except MetaNotConfiguredError as exc:
            return apply_delivery_to_message(message, {"delivered": False, "reason": str(exc)})
        except Exception as exc:
            logger.warning("Meta send failed: %s", exc)
            return apply_delivery_to_message(message, {"delivered": False, "reason": f"meta_error:{exc}"})

    if channel == ConversationChannel.WHATSAPP:
        # 1) Meta WhatsApp Cloud if connected
        creds = meta_page_credentials(db, conversation.shop_id)
        if creds and recipient:
            page_id, token = creds
            try:
                mid = send_messenger_text(page_id, token, recipient, text)
                return apply_delivery_to_message(
                    message, {"delivered": True, "provider_message_id": mid, "via": "whatsapp_cloud"}
                )
            except Exception as exc:
                logger.warning("WhatsApp Cloud send failed, trying Twilio: %s", exc)
        # 2) Twilio WhatsApp
        if recipient:
            try:
                sid = send_whatsapp(recipient, text)
                return apply_delivery_to_message(
                    message, {"delivered": True, "provider_message_id": sid, "via": "twilio_whatsapp"}
                )
            except MessagingNotConfiguredError:
                pass
            except Exception as exc:
                logger.warning("Twilio WhatsApp failed: %s", exc)
                return apply_delivery_to_message(message, {"delivered": False, "reason": f"wa_error:{exc}"})
        return apply_delivery_to_message(message, {"delivered": False, "reason": "whatsapp_not_connected"})

    if channel == ConversationChannel.TELEGRAM:
        cfg = _integration_config(db, conversation.shop_id, "telegram")
        bot_token = cfg.get("bot_token") or cfg.get("access_token")
        if not bot_token or not recipient:
            return apply_delivery_to_message(message, {"delivered": False, "reason": "telegram_not_connected"})
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": recipient, "text": text},
                timeout=20.0,
            )
            response.raise_for_status()
            mid = str((response.json().get("result") or {}).get("message_id") or "")
            return apply_delivery_to_message(
                message, {"delivered": True, "provider_message_id": mid, "via": "telegram"}
            )
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
            return apply_delivery_to_message(message, {"delivered": False, "reason": f"tg_error:{exc}"})

    return apply_delivery_to_message(
        message, {"delivered": False, "reason": f"channel_{channel.value}_local_only"}
    )


def deliver_outbound_image(
    db: Session,
    conversation: Conversation,
    image_url: str,
    *,
    message: Message | None = None,
    page_id: str | None = None,
) -> dict:
    """Send an actual image attachment (not just a URL as text) to the customer,
    on whichever channel supports it. Falls back to returning delivered=False so
    the caller can fall back to sending the URL as plain text instead."""
    if not image_url:
        return apply_delivery_to_message(message, {"delivered": False, "reason": "empty"})

    customer = db.get(Customer, conversation.customer_id)
    recipient = _external_id_from_customer(customer, conversation.channel)
    channel = conversation.channel
    absolute_image_url = media_absolute_url(image_url)

    if channel in (ConversationChannel.FACEBOOK, ConversationChannel.INSTAGRAM):
        if not recipient:
            return apply_delivery_to_message(message, {"delivered": False, "reason": "no_recipient"})
        resolved_page_id = page_id
        if not resolved_page_id and customer and customer.email and customer.email.startswith("page:"):
            resolved_page_id = customer.email.split(":", 1)[1]
        creds = meta_page_credentials(db, conversation.shop_id, page_id=resolved_page_id)
        if creds is None and resolved_page_id:
            creds = meta_page_credentials(db, conversation.shop_id, page_id=None)
        if creds is None:
            return apply_delivery_to_message(message, {"delivered": False, "reason": "meta_not_connected"})
        active_page_id, token = creds
        try:
            mid = send_messenger_image(active_page_id, token, recipient, absolute_image_url)
            return apply_delivery_to_message(
                message, {"delivered": True, "provider_message_id": mid, "via": "messenger_image"}
            )
        except MetaNotConfiguredError as exc:
            return apply_delivery_to_message(message, {"delivered": False, "reason": str(exc)})
        except Exception as exc:
            logger.warning("Meta image send failed: %s", exc)
            return apply_delivery_to_message(message, {"delivered": False, "reason": f"meta_error:{exc}"})

    if channel == ConversationChannel.TELEGRAM:
        cfg = _integration_config(db, conversation.shop_id, "telegram")
        bot_token = cfg.get("bot_token") or cfg.get("access_token")
        if not bot_token or not recipient:
            return apply_delivery_to_message(message, {"delivered": False, "reason": "telegram_not_connected"})
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                json={"chat_id": recipient, "photo": absolute_image_url},
                timeout=20.0,
            )
            response.raise_for_status()
            mid = str((response.json().get("result") or {}).get("message_id") or "")
            return apply_delivery_to_message(
                message, {"delivered": True, "provider_message_id": mid, "via": "telegram_photo"}
            )
        except Exception as exc:
            logger.warning("Telegram photo send failed: %s", exc)
            return apply_delivery_to_message(message, {"delivered": False, "reason": f"tg_error:{exc}"})

    # WhatsApp and other channels: no image-send wired up yet — caller falls back to text.
    return apply_delivery_to_message(
        message, {"delivered": False, "reason": f"channel_{channel.value}_image_unsupported"}
    )


def deliver_outbound_carousel(
    db: Session,
    conversation: Conversation,
    products: list[dict],
    *,
    message: Message | None = None,
    page_id: str | None = None,
) -> dict:
    """Send a scrollable multi-product card carousel (image/name/price per
    card) — Messenger-only for now, since it's Meta's own native template
    type; other channels fall back to delivered=False so the caller can show
    a plain text list instead."""
    if not products:
        return apply_delivery_to_message(message, {"delivered": False, "reason": "empty"})

    customer = db.get(Customer, conversation.customer_id)
    recipient = _external_id_from_customer(customer, conversation.channel)
    channel = conversation.channel

    if channel not in (ConversationChannel.FACEBOOK, ConversationChannel.INSTAGRAM):
        return apply_delivery_to_message(
            message, {"delivered": False, "reason": f"channel_{channel.value}_carousel_unsupported"}
        )
    if not recipient:
        return apply_delivery_to_message(message, {"delivered": False, "reason": "no_recipient"})

    resolved_page_id = page_id
    if not resolved_page_id and customer and customer.email and customer.email.startswith("page:"):
        resolved_page_id = customer.email.split(":", 1)[1]
    creds = meta_page_credentials(db, conversation.shop_id, page_id=resolved_page_id)
    if creds is None and resolved_page_id:
        creds = meta_page_credentials(db, conversation.shop_id, page_id=None)
    if creds is None:
        return apply_delivery_to_message(message, {"delivered": False, "reason": "meta_not_connected"})
    active_page_id, token = creds

    absolute_products = [
        {**p, "photo_url": media_absolute_url(p["photo_url"]) if p.get("photo_url") else None}
        for p in products
    ]
    try:
        mid = send_messenger_product_carousel(active_page_id, token, recipient, absolute_products)
        return apply_delivery_to_message(
            message, {"delivered": True, "provider_message_id": mid, "via": "messenger_carousel"}
        )
    except MetaNotConfiguredError as exc:
        return apply_delivery_to_message(message, {"delivered": False, "reason": str(exc)})
    except Exception as exc:
        logger.warning("Meta carousel send failed: %s", exc)
        return apply_delivery_to_message(message, {"delivered": False, "reason": f"meta_error:{exc}"})
