from app.services.webhook_routing import (
    is_meta_graph_payload,
    is_telegram_update,
    is_twilio_status_payload,
)


def test_meta_vs_twilio_whatsapp_shapes() -> None:
    meta = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": []}]}
    twilio = {"MessageStatus": "delivered", "MessageSid": "SMxxx", "AccountSid": "ACxxx"}
    assert is_meta_graph_payload(meta)
    assert not is_twilio_status_payload(meta)
    assert is_twilio_status_payload(twilio)
    assert not is_meta_graph_payload(twilio)


def test_telegram_update_shape() -> None:
    assert is_telegram_update({"update_id": 1, "message": {"chat": {"id": 9}, "text": "hi"}})
    assert not is_telegram_update({"MessageStatus": "sent"})


def test_whatsapp_provider_collision_rules() -> None:
    """Same provider name 'whatsapp' must route by body shape."""
    meta = {"object": "whatsapp_business_account", "entry": [{"id": "PAGE"}]}
    twilio = {"SmsStatus": "delivered", "SmsSid": "SMabc"}
    # Meta path
    assert is_meta_graph_payload(meta) and not is_twilio_status_payload(meta)
    # Twilio path
    assert is_twilio_status_payload(twilio) and not is_meta_graph_payload(twilio)
