"""Turns a confirmed chat conversation into a real Order (FR-CUST chat-to-order).

Previously "Chat-to-Order" was only a system-prompt instruction telling the AI
to *ask* for item/quantity/phone/address — nothing ever persisted an Order, so
a customer who "confirmed" got asked to order again next message and never
received a reference number. This module closes that gap: after every AI
auto-reply, it re-reads the whole conversation and, once it can clearly see a
confirmed item + quantity + phone + address, creates the Order and returns a
short reference to append to the reply.
"""
from __future__ import annotations

import json
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.integrations.llm import LLMNotConfiguredError, chat_completion
from app.models.conversation import Conversation, Message, MessageDirection
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.shop import Shop

logger = logging.getLogger(__name__)

ORDER_EXTRACTION_PROMPT = (
    "You extract confirmed order details from a customer support chat transcript. Decide "
    "whether the customer has clearly confirmed an order: named specific item(s), a quantity "
    "for each, a phone number, and a delivery address — and intends to proceed, not just asking "
    "questions or browsing.\n\n"
    "Return STRICT JSON only (no markdown, no backticks):\n"
    "{\n"
    '  "order_confirmed": boolean,\n'
    '  "items": [{"name": "exact item name as mentioned", "quantity": integer}],\n'
    '  "phone": "customer phone number (digits, spaces, + only) or null",\n'
    '  "address": "delivery address as given, or null"\n'
    "}\n"
    "If ANY of item name, quantity, phone, or address is missing, vague, or not yet confirmed, "
    "set 'order_confirmed' to false. Never invent details that were not actually said."
)


def short_order_ref(order_id: uuid.UUID) -> str:
    """Human-friendly reference from the order's own id — no separate counter needed."""
    return str(order_id).split("-")[0].upper()


def _next_invoice_number(db: Session, shop_id: uuid.UUID) -> str:
    """Sequential, human-readable invoice number the customer can read out to
    track their shipment — unlike the UUID-derived short ref, this is stable
    and ordered per shop."""
    count = db.query(Order).filter(Order.shop_id == shop_id).count()
    return f"INV-{count + 1:06d}"


def _build_transcript(messages: list[Message]) -> str:
    lines = []
    for m in messages:
        if not m.text:
            continue
        speaker = "Customer" if m.direction == MessageDirection.INBOUND else "Shop"
        lines.append(f"{speaker}: {m.text.strip()}")
    return "\n".join(lines)


def _match_product(db: Session, shop_id: uuid.UUID, name: str) -> Product | None:
    name = (name or "").strip()
    if not name:
        return None
    return (
        db.query(Product)
        .filter(Product.shop_id == shop_id, Product.kind == "product", Product.name.ilike(f"%{name}%"))
        .order_by(Product.created_at.desc())
        .first()
    )


def try_confirm_order_from_chat(db: Session, shop: Shop, conversation: Conversation) -> str | None:
    """If this conversation now contains a clearly confirmed, matchable order,
    create it (once) and return a customer-facing confirmation message to
    append to the AI's reply. Returns None if no order should be created/mentioned.
    """
    existing = db.query(Order).filter(Order.conversation_id == conversation.id).first()
    if existing:
        ref = existing.invoice_number or short_order_ref(existing.id)
        # Already confirmed earlier in this same conversation — remind, don't duplicate.
        return f"(Invoice {ref} is already on file for this conversation.)"

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(30)
        .all()
    )
    transcript = _build_transcript(messages)
    if not transcript:
        return None

    try:
        raw = chat_completion(ORDER_EXTRACTION_PROMPT, transcript, max_tokens=300)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
    except LLMNotConfiguredError:
        return None
    except Exception as exc:
        logger.debug("Order extraction parse failed: %s", exc)
        return None

    if not isinstance(data, dict) or not data.get("order_confirmed"):
        return None

    items_in = data.get("items") or []
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    if not items_in or not phone or not address:
        return None

    order_items: list[OrderItem] = []
    total = 0.0
    for item in items_in:
        product = _match_product(db, shop.id, str(item.get("name") or ""))
        if product is None:
            continue
        qty = max(1, int(item.get("quantity") or 1))
        unit_price = float(product.price)
        order_items.append(
            OrderItem(
                name_snapshot=product.name,
                quantity=qty,
                unit_price=unit_price,
                unit_cost_snapshot=float(product.cost) if product.cost is not None else None,
            )
        )
        total += unit_price * qty

    if not order_items:
        # Couldn't match anything the customer named to the real catalog —
        # don't silently create an empty order; let the conversation continue.
        return None

    order = Order(
        shop_id=shop.id,
        customer_id=conversation.customer_id,
        status=OrderStatus.NEW,
        source_channel="chat",
        total_amount=total,
        conversation_id=conversation.id,
        customer_phone=phone,
        delivery_address=address,
        invoice_number=_next_invoice_number(db, shop.id),
        items=order_items,
    )
    db.add(order)
    db.flush()

    currency = shop.currency or "BDT"
    summary = ", ".join(f"{i.quantity}x {i.name_snapshot}" for i in order_items)
    return (
        f"✅ Order received! Invoice number: {order.invoice_number} — use this to track your shipment.\n"
        f"Items: {summary}\n"
        f"Total: {total:.2f} {currency}\n"
        f"We'll contact you at {phone} and deliver to: {address}. The seller will confirm your order shortly."
    )
