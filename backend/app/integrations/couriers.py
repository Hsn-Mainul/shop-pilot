"""Courier booking adapters (Pathao / Steadfast). Uses live API when credentials
exist on the Integration; otherwise returns an honest local stub tracking id.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)


def book_parcel(
    courier: str,
    *,
    config: dict,
    order_id: uuid.UUID,
    cod_amount: Decimal,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    address: str | None = None,
) -> dict:
    courier_l = (courier or "").lower()
    if courier_l == "pathao" and config.get("api_key") and config.get("store_id"):
        return _pathao_book(config, order_id, cod_amount, recipient_name, recipient_phone, address)
    if courier_l == "steadfast" and config.get("api_key") and config.get("secret_key"):
        return _steadfast_book(config, order_id, cod_amount, recipient_name, recipient_phone, address)
    # Honest stub — merchant can still track locally until credentials are set
    tracking = f"{courier_l.upper() or 'LOCAL'}-{str(order_id)[:8].upper()}"
    return {
        "tracking_id": tracking,
        "status": "to_book",
        "stub": True,
        "message": "Courier API credentials not configured; booked locally.",
    }


def _pathao_book(config, order_id, cod_amount, name, phone, address) -> dict:
    base = config.get("base_url") or "https://api-hermes.pathao.com"
    try:
        response = httpx.post(
            f"{base}/aladdin/api/v1/orders",
            headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
            json={
                "store_id": config["store_id"],
                "merchant_order_id": str(order_id),
                "recipient_name": name or "Customer",
                "recipient_phone": phone or "01000000000",
                "recipient_address": address or "Address pending",
                "delivery_type": 48,
                "item_type": 2,
                "item_quantity": 1,
                "item_weight": 0.5,
                "amount_to_collect": float(cod_amount),
            },
            timeout=25.0,
        )
        if response.status_code >= 400:
            logger.warning("Pathao book failed: %s", response.text[:200])
            return book_parcel("pathao", config={}, order_id=order_id, cod_amount=cod_amount)
        data = response.json().get("data") or response.json()
        return {
            "tracking_id": str(data.get("consignment_id") or data.get("tracking_id") or order_id),
            "status": "to_book",
            "stub": False,
        }
    except Exception as exc:
        logger.warning("Pathao error: %s", exc)
        return book_parcel("pathao", config={}, order_id=order_id, cod_amount=cod_amount)


def _steadfast_book(config, order_id, cod_amount, name, phone, address) -> dict:
    base = config.get("base_url") or "https://portal.packzy.com/api/v1"
    try:
        response = httpx.post(
            f"{base}/create_order",
            headers={
                "Api-Key": config["api_key"],
                "Secret-Key": config["secret_key"],
                "Content-Type": "application/json",
            },
            json={
                "invoice": str(order_id),
                "recipient_name": name or "Customer",
                "recipient_phone": phone or "01000000000",
                "recipient_address": address or "Address pending",
                "cod_amount": float(cod_amount),
            },
            timeout=25.0,
        )
        if response.status_code >= 400:
            logger.warning("Steadfast book failed: %s", response.text[:200])
            return book_parcel("steadfast", config={}, order_id=order_id, cod_amount=cod_amount)
        data = response.json()
        tracking = (data.get("consignment") or {}).get("tracking_code") or data.get("tracking_code")
        return {"tracking_id": str(tracking or order_id), "status": "to_book", "stub": False}
    except Exception as exc:
        logger.warning("Steadfast error: %s", exc)
        return book_parcel("steadfast", config={}, order_id=order_id, cod_amount=cod_amount)
