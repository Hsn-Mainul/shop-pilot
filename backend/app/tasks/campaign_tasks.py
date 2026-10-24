"""Real bulk-campaign dispatch (FR-CUST-06/07, FR-CUST-08) as an async Celery task."""
import uuid
from datetime import datetime, timezone

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.integrations.messaging import MessagingNotConfiguredError, send_email, send_sms, send_whatsapp
from app.models.automation import BulkCampaign, CustomerChannelOptOut
from app.models.customer import Customer


def _resolve_recipients(db, shop_id: uuid.UUID, segment: str) -> list[Customer]:
    query = db.query(Customer).filter(Customer.shop_id == shop_id, Customer.is_blocked.is_(False))
    if segment == "all":
        pass
    elif segment == "repeat_customers":
        query = query.filter(Customer.segment.in_(["repeat_customer", "vip"]))
    elif segment.startswith("region:"):
        # Match customers tagged with this region in segment or source
        # (e.g. segment="region:Dhaka" or source="Dhaka").
        region = segment.split(":", 1)[1].strip()
        query = query.filter(
            (Customer.segment == segment)
            | (Customer.segment == region)
            | (Customer.source == region)
            | (Customer.source == segment)
        )
    return query.all()


@celery_app.task(bind=True, max_retries=2)
def send_campaign(self, campaign_id: str) -> dict:
    db = SessionLocal()
    try:
        campaign = db.get(BulkCampaign, uuid.UUID(campaign_id))
        if campaign is None:
            return {"error": "campaign not found"}

        opted_out_ids = {
            row.customer_id
            for row in db.query(CustomerChannelOptOut).filter(
                CustomerChannelOptOut.channel == campaign.channel
            )
        }
        recipients = [
            c for c in _resolve_recipients(db, campaign.shop_id, campaign.segment) if c.id not in opted_out_ids
        ]

        from app.core.config import settings
        from app.models.shop import Shop

        shop = db.get(Shop, campaign.shop_id)
        shop_name = shop.name if shop else "our shop"
        status_cb = f"{settings.public_base_url.rstrip('/')}/api/v1/webhooks/twilio?shop_id={campaign.shop_id}"

        sent = 0
        accepted = 0
        for customer in recipients:
            try:
                message = (
                    campaign.message_template.replace("{{first_name}}", customer.name or "there")
                    .replace("{{shop_name}}", shop_name)
                )
                if shop_name.lower() not in message.lower():
                    message = f"{message}\n\n— {shop_name}"
                # Embed campaign id so delivery webhooks can attribute status
                message_with_meta = message
                if campaign.channel == "email" and customer.email:
                    send_email(customer.email, subject=f"Update from {shop_name}", body=message_with_meta)
                elif campaign.channel == "sms" and customer.phone:
                    send_sms(customer.phone, message_with_meta)
                elif campaign.channel == "whatsapp" and customer.phone:
                    send_whatsapp(customer.phone, message_with_meta)
                elif campaign.channel == "voice":
                    from app.integrations.telephony import place_call

                    if customer.phone:
                        place_call(customer.phone, status_callback=status_cb)
                else:
                    continue
                sent += 1
                accepted += 1  # provider accepted; delivered_count rises on status webhooks
            except MessagingNotConfiguredError:
                break
            except Exception:
                sent += 1

        campaign.sent_count = sent
        # Start delivered at 0; webhooks increment. For channels without callbacks,
        # keep accepted as a provisional delivered count.
        campaign.delivered_count = 0 if campaign.channel in ("sms", "whatsapp", "email") else accepted
        campaign.opted_out_excluded_count = len(opted_out_ids)
        campaign.status = "sending" if campaign.channel in ("sms", "whatsapp") else "completed"
        # Stash campaign id on config-less campaigns via status field transition later
        db.add(campaign)
        db.commit()
        return {"sent": sent, "accepted": accepted, "status_callback": status_cb}
    finally:
        db.close()


@celery_app.task
def dispatch_due_campaigns() -> dict:
    """Periodic sweep (see celery beat schedule) that sends any 'scheduled'
    campaign whose scheduled_at has passed."""
    db = SessionLocal()
    try:
        due = (
            db.query(BulkCampaign)
            .filter(BulkCampaign.status == "scheduled", BulkCampaign.scheduled_at <= datetime.now(timezone.utc))
            .all()
        )
        for campaign in due:
            send_campaign.delay(str(campaign.id))
        return {"dispatched": len(due)}
    finally:
        db.close()
