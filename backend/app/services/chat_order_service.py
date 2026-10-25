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
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.integrations.llm import LLMNotConfiguredError, chat_completion
from app.models.conversation import Conversation, Message, MessageDirection
from app.models.delivery import DeliveryParcel
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.shop import Shop

logger = logging.getLogger(__name__)

# How long an unfinished order attempt (phone/address given, no Order created yet)
# stays "live" before it's treated as abandoned and no longer eligible to be
# silently confirmed by a later, unrelated message.
ORDER_ATTEMPT_STALE_AFTER = timedelta(minutes=15)

ORDER_EXTRACTION_PROMPT = (
    "You extract confirmed order details from a customer support chat transcript. Decide "
    "whether the customer has clearly confirmed an order: named specific item(s), a quantity "
    "for each, a phone number, and a delivery address.\n\n"
    "IMPORTANT: a customer giving their phone number and delivery address together with an item "
    "and quantity IS itself a clear, strong signal they intend to order — that's what placing an "
    "order over chat normally looks like. Do not require an explicit word like 'yes', 'confirm', or "
    "'order' to appear — judge intent from the item+quantity+phone+address being given together, "
    "even if an earlier message in the same transcript was just a question (e.g. 'is this available?' "
    "followed by their item/phone/address is a confirmed order, not just browsing).\n\n"
    "Return STRICT JSON only (no markdown, no backticks):\n"
    "{\n"
    '  "order_confirmed": boolean,\n'
    '  "items": [{"name": "exact item name as mentioned", "quantity": integer}],\n'
    '  "phone": "customer phone number (digits, spaces, + only) or null",\n'
    '  "address": "delivery address as given, or null"\n'
    "}\n"
    "If ANY of item name, quantity, phone, or address is missing or vague, set 'order_confirmed' to "
    "false. Never invent details that were not actually said."
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
    """Match the item name the customer/LLM extracted from chat to a real
    catalog product. A plain substring match is too brittle for this — it
    silently fails on anything the customer phrases slightly differently
    from the stored name (e.g. "tshirt" vs "T-Shirt", where the hyphen alone
    breaks a substring match), which previously caused orders to silently
    never get created while the AI still told the customer it was confirmed.
    Falls back to the existing semantic/lexical catalog search instead.
    """
    name = (name or "").strip()
    if not name:
        return None

    exact = (
        db.query(Product)
        .filter(Product.shop_id == shop_id, Product.kind == "product", Product.name.ilike(f"%{name}%"))
        .order_by(Product.created_at.desc())
        .first()
    )
    if exact:
        return exact

    from app.services.rag_service import search_knowledge_and_catalog

    res = search_knowledge_and_catalog(
        db, shop_id, name, top_k_knowledge=0, top_k_products=1, min_similarity=0.3
    )
    products = res.get("products") or []
    if not products:
        return None
    return db.get(Product, products[0]["id"])


def try_confirm_order_from_chat(db: Session, shop: Shop, conversation: Conversation) -> str | None:
    """If this conversation now contains a clearly confirmed, matchable order,
    create it and return a customer-facing confirmation message to append to
    the AI's reply. Returns None if no order should be created/mentioned.

    A conversation can place more than one order over time (a customer may
    order again later), so this only looks at messages SENT AFTER the most
    recent order already created for this conversation — never re-reading an
    old, already-fulfilled order's item/phone/address back out of history as
    if it were a fresh confirmation. That previously caused the bot to repeat
    "an order is already on file" on every later message, even ones that had
    nothing to do with ordering.

    It also never looks further back than ORDER_ATTEMPT_STALE_AFTER — if a
    customer gave their phone/address a while ago but no order ever actually
    got created from it (e.g. the item couldn't be matched at the time), and
    the conversation has since moved on to something unrelated, that old
    info is stale and must not get silently "confirmed" by a later, unrelated
    message just because it's still sitting in the lookback window.
    """
    last_order = (
        db.query(Order)
        .filter(Order.conversation_id == conversation.id)
        .order_by(Order.created_at.desc())
        .first()
    )

    staleness_cutoff = datetime.now(timezone.utc) - ORDER_ATTEMPT_STALE_AFTER
    window_start = max(last_order.created_at, staleness_cutoff) if last_order is not None else staleness_cutoff

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.created_at > window_start)
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
        # The customer isn't confirming a (new) order on THIS turn — e.g. just asking about
        # availability or a photo. Stay silent; nothing to create or remind about.
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


# ---------------------------------------------------------------------------
# Regex that recognises "track / where is / status of" + an invoice reference
# e.g. "track my order INV-000042", "where is INV000042", "order status INV-7"
# ---------------------------------------------------------------------------
_TRACK_INTENT = re.compile(
    r"(?:track|where.{0,10}order|order.{0,10}status|shipment|delivery\s+status)",
    re.I,
)
_INVOICE_RE = re.compile(r"INV[-\s]?(\d+)", re.I)

# Human-readable labels for DeliveryParcel.status values
_PARCEL_STATUS_LABELS: dict[str, str] = {
    "to_book": "Waiting to be booked with courier",
    "picked_up": "Picked up by courier",
    "in_transit": "In transit",
    "out_for_delivery": "Out for delivery — arriving today",
    "delivered": "Delivered",
    "returned": "Returned to seller",
    "on_hold": "On hold",
}


def _order_status_label(status: OrderStatus) -> str:
    return {
        OrderStatus.NEW: "Received — waiting for seller confirmation",
        OrderStatus.CONFIRMED: "Confirmed by seller — being prepared",
        OrderStatus.DECLINED: "Declined by seller",
        OrderStatus.PACKED: "Packed and ready to ship",
        OrderStatus.SHIPPED: "Shipped",
        OrderStatus.DELIVERED: "Delivered",
        OrderStatus.RETURNED: "Returned",
        OrderStatus.ON_HOLD: "On hold",
    }.get(status, status.value)


def try_track_order_from_chat(
    db: Session,
    shop: Shop,
    text: str,
    customer_id: uuid.UUID,
) -> str | None:
    """If the customer's message is a tracking request (contains a tracking
    intent keyword + an invoice number, or just a bare invoice number with
    a clear tracking intent), look up the order and return a status message.

    Returns None when the message isn't a tracking request so the normal RAG
    path can continue uninterrupted.
    """
    # Must look like a tracking query
    has_track_intent = bool(_TRACK_INTENT.search(text))
    invoice_match = _INVOICE_RE.search(text)

    # Accept "track INV-000042" OR a bare invoice number from the same customer
    if not invoice_match:
        # No invoice number — only respond if the message is explicitly asking
        # to track without specifying which order (look up their latest order).
        if not has_track_intent:
            return None
        # Find most recent order for this customer in this shop
        order = (
            db.query(Order)
            .filter(Order.shop_id == shop.id, Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .first()
        )
        if order is None:
            return None
    else:
        # Normalise: "INV000042" -> "INV-000042"
        digits = invoice_match.group(1).lstrip("0") or "0"
        padded = f"INV-{digits.zfill(6)}"
        order = (
            db.query(Order)
            .filter(Order.shop_id == shop.id, Order.invoice_number == padded)
            .first()
        )
        if order is None:
            # Maybe they typed partial digits — fuzzy match
            order = (
                db.query(Order)
                .filter(
                    Order.shop_id == shop.id,
                    Order.invoice_number.ilike(f"%{digits}%"),
                )
                .order_by(Order.created_at.desc())
                .first()
            )
        if order is None:
            return (
                f"I couldn't find an order matching that invoice number. "
                f"Please double-check and try again, or contact support."
            )

    # Security: only let the customer who placed the order track it
    if order.customer_id != customer_id:
        return (
            "I couldn't find an order with that reference on your account. "
            "Please check the invoice number and try again."
        )

    ref = order.invoice_number or short_order_ref(order.id)
    order_status_text = _order_status_label(order.status)

    # Check if a delivery parcel exists for richer status
    parcel = (
        db.query(DeliveryParcel)
        .filter(DeliveryParcel.order_id == order.id)
        .order_by(DeliveryParcel.created_at.desc())
        .first()
    )

    lines = [f"Order {ref} — Status: {order_status_text}"]

    if parcel:
        parcel_label = _PARCEL_STATUS_LABELS.get(
            parcel.status.value if hasattr(parcel.status, "value") else str(parcel.status),
            str(parcel.status),
        )
        lines.append(f"Delivery: {parcel_label}")
        if parcel.courier:
            lines.append(f"Courier: {parcel.courier.capitalize()}")
        if parcel.tracking_id:
            lines.append(f"Courier tracking ID: {parcel.tracking_id}")

    if order.delivery_address:
        lines.append(f"Delivery address: {order.delivery_address}")

    currency = shop.currency or "BDT"
    lines.append(f"Order total: {float(order.total_amount):.2f} {currency}")

    return "\n".join(lines)
