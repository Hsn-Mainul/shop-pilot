"""Classify inbound webhook payloads so provider aliases do not collide."""


def is_meta_graph_payload(payload: dict) -> bool:
    """Meta Messenger / IG / WhatsApp Cloud use entry[] (+ often object)."""
    if not isinstance(payload, dict):
        return False
    if payload.get("object") in ("page", "instagram", "whatsapp_business_account"):
        return True
    entry = payload.get("entry")
    return isinstance(entry, list) and len(entry) > 0


def is_twilio_status_payload(payload: dict) -> bool:
    """Twilio SMS/WhatsApp delivery callbacks (form or JSON)."""
    if not isinstance(payload, dict):
        return False
    keys = {str(k).lower() for k in payload}
    return bool(
        keys
        & {
            "messagestatus",
            "smsstatus",
            "messagesid",
            "smssid",
            "accountsid",
        }
    )


def is_telegram_update(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    return "update_id" in payload or "message" in payload or "edited_message" in payload
