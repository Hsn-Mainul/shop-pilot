"""In-process automation rule execution (FR-AUTO-01/02/03).

This is a synchronous, in-request dispatcher rather than a Celery/event-bus
worker — see the README's Known Gaps for why a real background-job queue is
still a separate piece of work. What IS real here: active rules matching a
trigger genuinely execute their action and the rule's run/failure counters
and the Automation Overview stats are genuinely accurate, not placeholders.

Call `trigger_event(db, shop_id, event_name, context)` from any endpoint that
completes an action a rule might care about (e.g. order confirmed, stock low).
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.automation import AutomationRule

logger = logging.getLogger(__name__)


def _enforce_shop_brand(db: Session, shop_id, text: str) -> str:
    """FR: shop brand name must appear in automated outbound messages."""
    from app.models.shop import Shop

    shop = db.get(Shop, shop_id)
    if shop is None or not shop.name:
        return text
    if shop.name.lower() in (text or "").lower():
        return text
    return f"{text}\n\n— {shop.name}"


def _action_send_saved_reply(db: Session, rule: AutomationRule, context: dict[str, Any]) -> None:
    from app.models.conversation import Message, MessageDirection
    from app.models.saved_reply import SavedReply

    conversation_id = context.get("conversation_id")
    if conversation_id is None:
        raise ValueError("send_saved_reply action requires context['conversation_id']")

    shortcut = rule.config.get("shortcut")
    reply = (
        db.query(SavedReply)
        .filter(SavedReply.shop_id == rule.shop_id, SavedReply.shortcut == shortcut)
        .first()
    )
    if reply is None:
        raise ValueError(f"No saved reply with shortcut '{shortcut}' for this shop")

    body = reply.body.replace("{{shop_name}}", "")
    # Re-inject via enforcer so brand is never omitted even if template forgot it.
    from app.models.shop import Shop

    shop = db.get(Shop, rule.shop_id)
    if shop:
        body = reply.body.replace("{{shop_name}}", shop.name)
    body = _enforce_shop_brand(db, rule.shop_id, body)

    db.add(
        Message(
            conversation_id=conversation_id,
            direction=MessageDirection.OUTBOUND,
            text=body,
            sent_by_ai=True,
        )
    )
    reply.usage_count += 1
    db.add(reply)


def _action_create_support_request(db: Session, rule: AutomationRule, context: dict[str, Any]) -> None:
    from app.models.support import SupportRequest

    db.add(
        SupportRequest(
            shop_id=rule.shop_id,
            created_by=context["actor_id"],
            subject=rule.config.get("subject", f"Automation: {rule.name}"),
            body=rule.config.get("body", "Auto-raised by an automation rule.") + f"\nContext: {context}",
        )
    )


def _action_flag_data_hygiene(db: Session, rule: AutomationRule, context: dict[str, Any]) -> None:
    from app.models.team_ops import DataHygieneIssue, DataHygieneIssueType

    db.add(
        DataHygieneIssue(
            shop_id=rule.shop_id,
            issue_type=DataHygieneIssueType(rule.config.get("issue_type", "missing_price")),
            related_id=context["related_id"],
        )
    )


ACTION_HANDLERS = {
    "send_saved_reply": _action_send_saved_reply,
    "create_support_request": _action_create_support_request,
    "flag_data_hygiene": _action_flag_data_hygiene,
}


def trigger_event(db: Session, shop_id, event_name: str, context: dict[str, Any] | None = None) -> list[AutomationRule]:
    """Run every active rule for this shop whose trigger matches `event_name`.

    Returns the rules that were evaluated (whether they succeeded or failed);
    each rule's run_count/failure_count is updated and committed.
    """
    context = context or {}
    rules = (
        db.query(AutomationRule)
        .filter(
            AutomationRule.shop_id == shop_id,
            AutomationRule.trigger == event_name,
            AutomationRule.is_active.is_(True),
        )
        .all()
    )

    for rule in rules:
        handler = ACTION_HANDLERS.get(rule.action)
        rule.run_count += 1
        if handler is None:
            rule.failure_count += 1
            logger.warning("Automation rule %s has unknown action '%s'", rule.id, rule.action)
            continue
        try:
            handler(db, rule, context)
        except Exception:
            rule.failure_count += 1
            logger.exception("Automation rule %s failed on event '%s'", rule.id, event_name)
        db.add(rule)

    if rules:
        db.commit()
    return rules
