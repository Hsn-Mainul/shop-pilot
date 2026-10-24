"""Unit tests for Meta/Telegram payload normalization (no DB required)."""
from app.services.inbox_ingest import parse_meta_messaging_payload


def test_parse_messenger_text() -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE1",
                "messaging": [
                    {
                        "sender": {"id": "USER123"},
                        "message": {"text": "price koto?"},
                    }
                ],
            }
        ],
    }
    items = parse_meta_messaging_payload(payload)
    assert len(items) == 1
    assert items[0]["external_user_id"] == "USER123"
    assert items[0]["text"] == "price koto?"
    assert items[0]["channel"] == "facebook"


def test_parse_skips_echo() -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "PAGE"},
                        "message": {"text": "hi", "is_echo": True},
                    }
                ]
            }
        ],
    }
    assert parse_meta_messaging_payload(payload) == []


def test_parse_feed_comment() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "feed",
                        "value": {
                            "comment_id": "c1",
                            "from": {"id": "U9", "name": "Asha"},
                            "message": "nice product",
                        },
                    }
                ]
            }
        ]
    }
    items = parse_meta_messaging_payload(payload)
    assert len(items) == 1
    assert items[0]["channel"] == "comment"
    assert items[0]["comment_id"] == "c1"
    assert items[0]["name"] == "Asha"


def test_channel_outbound_apply_delivery() -> None:
    from types import SimpleNamespace

    from app.services.channel_outbound import apply_delivery_to_message

    msg = SimpleNamespace(delivery_status=None, delivery_detail=None)
    apply_delivery_to_message(msg, {"delivered": True, "via": "messenger"})
    assert msg.delivery_status == "sent"
    assert msg.delivery_detail == "messenger"

    apply_delivery_to_message(msg, {"delivered": False, "reason": "meta_not_connected"})
    assert msg.delivery_status == "failed"
    assert "meta_not_connected" in msg.delivery_detail
