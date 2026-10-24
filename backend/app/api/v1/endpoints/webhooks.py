import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.automation import BulkCampaign
from app.models.finance import LedgerAccountType, LedgerEntry
from app.models.integration import Integration
from app.models.order import Order
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.webhook_event import WebhookEvent
from app.realtime.hub import hub
from app.models.conversation import ConversationChannel
from app.models.integration import IntegrationStatus
from app.services.inbox_ingest import apply_meta_inbound, ingest_inbound_message, resolve_shop_id_for_meta
from app.services.webhook_routing import is_meta_graph_payload, is_telegram_update, is_twilio_status_payload
from app.services.webhook_signatures import ALGORITHM_VERIFIERS, PROVIDER_VERIFIERS, verify_with_algo


def _resolve_telegram_shop_id(
    db: Session,
    shop_id: uuid.UUID | None,
    *,
    secret_header: str | None = None,
) -> uuid.UUID | None:
    """Resolve shop from query param, secret-token header, or single connected bot."""
    if shop_id is not None:
        return shop_id
    integrations = (
        db.query(Integration)
        .filter(
            Integration.provider == "telegram",
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .all()
    )
    if secret_header:
        for integ in integrations:
            cfg = integ.config or {}
            expected = cfg.get("webhook_secret") or cfg.get("secret_token")
            if expected and expected == secret_header:
                return integ.shop_id
    if len(integrations) == 1:
        return integrations[0].shop_id
    return None


def _apply_telegram_inbound(db: Session, shop_id: uuid.UUID | None, payload: dict) -> int:
    """Telegram Bot API update → inbox message."""
    if shop_id is None:
        return 0
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or message.get("caption")
    if not chat_id:
        return 0
    from_user = message.get("from") or {}
    name = " ".join(
        p for p in [from_user.get("first_name"), from_user.get("last_name")] if p
    ) or from_user.get("username")
    msg = ingest_inbound_message(
        db,
        shop_id,
        channel=ConversationChannel.TELEGRAM,
        external_user_id=str(chat_id),
        text=text,
        name=name,
    )
    return 1 if msg else 0

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/meta")
@router.get("/facebook")
@router.get("/instagram")
async def meta_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Meta webhook subscription verification handshake."""
    expected = settings.meta_webhook_verify_token or settings.meta_app_secret
    if hub_mode == "subscribe" and expected and hub_verify_token == expected and hub_challenge:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="verification failed", status_code=403, media_type="text/plain")


def _apply_campaign_status(db: Session, payload: dict, shop_id: uuid.UUID | None = None) -> bool:
    """Twilio/MessageBird-style delivery callbacks → campaign delivered_count."""
    campaign_id = payload.get("campaign_id") or (payload.get("extra") or {}).get("campaign_id")
    message_status = (
        payload.get("MessageStatus")
        or payload.get("SmsStatus")
        or payload.get("status")
        or payload.get("event")
        or ""
    ).lower()
    if message_status not in ("delivered", "read", "delivery", "sent"):
        return False

    campaign = None
    if campaign_id:
        try:
            campaign = db.get(BulkCampaign, uuid.UUID(str(campaign_id)))
        except ValueError:
            campaign = None
    if campaign is None and shop_id is not None:
        campaign = (
            db.query(BulkCampaign)
            .filter(BulkCampaign.shop_id == shop_id, BulkCampaign.status.in_(["sending", "scheduled"]))
            .order_by(BulkCampaign.created_at.desc())
            .first()
        )
    if campaign is None:
        return False

    if message_status in ("delivered", "read", "delivery"):
        campaign.delivered_count = (campaign.delivered_count or 0) + 1
        if campaign.delivered_count >= (campaign.sent_count or 0) > 0:
            campaign.status = "completed"
    db.add(campaign)
    hub.broadcast_sync(campaign.shop_id, "campaign.updated", {"campaign_id": str(campaign.id)})
    return True


def _apply_payment_gateway(db: Session, shop_id: uuid.UUID | None, provider: str, payload: dict) -> bool:
    """Auto-match gateway webhooks (bkash/stripe/nagad) to pending payments (FR-PAY-02)."""
    trx = (
        payload.get("trx_id")
        or payload.get("transaction_id")
        or payload.get("payment_intent")
        or payload.get("id")
        or payload.get("trxID")
    )
    amount_raw = payload.get("amount") or payload.get("Amount") or payload.get("value")
    if trx is None or amount_raw is None:
        return False
    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        return False

    query = db.query(Payment).join(Order)
    if shop_id:
        query = query.filter(Order.shop_id == shop_id)
    payment = (
        query.filter(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.NEEDS_REVIEW]),
            Payment.trx_ref == str(trx),
        )
        .first()
    )
    if payment is None:
        # Amount + method heuristic when trx not pre-recorded
        method_map = {
            "bkash": PaymentMethod.BKASH,
            "nagad": PaymentMethod.NAGAD,
            "stripe": PaymentMethod.CARD,
            "sslcommerz": PaymentMethod.CARD,
        }
        method = method_map.get(provider)
        q2 = db.query(Payment).join(Order).filter(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.NEEDS_REVIEW]),
            Payment.amount == amount,
        )
        if shop_id:
            q2 = q2.filter(Order.shop_id == shop_id)
        if method:
            q2 = q2.filter(Payment.method == method)
        payment = q2.order_by(Payment.created_at.desc()).first()

    if payment is None:
        return False

    payment.trx_ref = payment.trx_ref or str(trx)
    payment.status = PaymentStatus.CONFIRMED
    payment.note = (payment.note or "") + f" | auto-matched via {provider} webhook"
    db.add(payment)
    order = db.get(Order, payment.order_id)
    if order:
        ledger_account = {
            PaymentMethod.CASH: LedgerAccountType.CASH,
            PaymentMethod.COD: LedgerAccountType.CASH,
            PaymentMethod.BKASH: LedgerAccountType.WALLET,
            PaymentMethod.NAGAD: LedgerAccountType.WALLET,
            PaymentMethod.BANK: LedgerAccountType.BANK,
            PaymentMethod.CARD: LedgerAccountType.BANK,
        }.get(payment.method, LedgerAccountType.CASH)
        db.add(
            LedgerEntry(
                shop_id=order.shop_id,
                account_type=ledger_account,
                amount=payment.amount,
                ref_type="payment",
                ref_id=payment.id,
            )
        )
        hub.broadcast_sync(order.shop_id, "payment.confirmed", {"payment_id": str(payment.id)})
    return True


@router.post("/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(provider: str, request: Request, shop_id: uuid.UUID | None = None) -> dict:
    """Generic inbound webhook receiver for any connected provider."""
    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        # Twilio often posts form-encoded status callbacks
        form = await request.form()
        payload = dict(form)

    db: Session = SessionLocal()
    try:
        verified = False
        integration = None
        if shop_id is not None:
            integration = (
                db.query(Integration)
                .filter(Integration.shop_id == shop_id, Integration.provider == provider)
                .first()
            )
        if shop_id is not None and integration:
            cfg = integration.config or {}
            secret = cfg.get("webhook_secret") or cfg.get("app_secret") or cfg.get("auth_token")
            if secret:
                # Exotic / shop-configured scheme via signature_algo + signature_header
                algo = cfg.get("signature_algo")
                if algo and algo in ALGORITHM_VERIFIERS:
                    header_name = cfg.get("signature_header") or "X-Signature"
                    header_value = request.headers.get(header_name)
                    verified = verify_with_algo(algo, raw_body, header_value, secret)
                elif provider in PROVIDER_VERIFIERS:
                    verifier, header_name = PROVIDER_VERIFIERS[provider]
                    header_value = request.headers.get(header_name)
                    verified = verifier(raw_body, header_value, secret)

        event = WebhookEvent(
            provider=provider,
            shop_id=shop_id,
            payload=payload if isinstance(payload, dict) else {"raw": str(payload)},
            signature_verified=verified,
        )
        db.add(event)

        applied = False
        ingested = 0
        if isinstance(payload, dict):
            # Campaign / Twilio delivery receipts — never Meta-shaped
            campaign_providers = ("twilio", "sms", "email", "campaign", "whatsapp-twilio")
            if provider in campaign_providers or (
                provider == "whatsapp" and is_twilio_status_payload(payload) and not is_meta_graph_payload(payload)
            ):
                applied = _apply_campaign_status(db, payload, shop_id) or applied

            if provider in ("bkash", "nagad", "stripe", "sslcommerz", "payment"):
                applied = _apply_payment_gateway(db, shop_id, provider, payload) or applied

            # Meta Graph messaging — never Twilio status forms
            meta_providers = ("meta", "facebook", "instagram", "messenger", "whatsapp-meta")
            if provider in meta_providers or (
                provider == "whatsapp" and is_meta_graph_payload(payload)
            ):
                resolved = resolve_shop_id_for_meta(db, payload, shop_id)
                if resolved:
                    shop_id = resolved
                    event.shop_id = resolved
                    ingested = apply_meta_inbound(db, resolved, payload)
                    applied = applied or ingested > 0

            if provider == "telegram" or (provider == "telegram-bot" and is_telegram_update(payload)):
                tg_shop = _resolve_telegram_shop_id(
                    db,
                    shop_id,
                    secret_header=request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
                )
                if tg_shop:
                    event.shop_id = tg_shop
                    ingested = _apply_telegram_inbound(db, tg_shop, payload)
                    applied = applied or ingested > 0

        db.commit()
        db.refresh(event)
        return {
            "received": True,
            "event_id": str(event.id),
            "signature_verified": verified,
            "applied": applied,
            "messages_ingested": ingested,
        }
    finally:
        db.close()
