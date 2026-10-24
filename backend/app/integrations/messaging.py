"""Real outbound SMS/WhatsApp (Twilio) and email (SMTP) senders, for bulk
campaigns (FR-CUST-06/07) and transactional notifications.
"""
import smtplib
from email.mime.text import MIMEText

import httpx

from app.core.config import settings


class MessagingNotConfiguredError(RuntimeError):
    pass


def send_sms(to_number: str, body: str) -> str:
    if not settings.twilio_configured or not settings.twilio_from_number:
        raise MessagingNotConfiguredError("Twilio SMS is not configured")
    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={"To": to_number, "From": settings.twilio_from_number, "Body": body},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()["sid"]


def send_whatsapp(to_number: str, body: str) -> str:
    """FR-CUST-07: bulk WhatsApp. `to_number`/`from` must be in Twilio's
    'whatsapp:+...' format. Template-message approval (required by WhatsApp's
    own policy for the first message in a 24h window) is the Shop's
    responsibility to pre-approve with the provider; this call sends the
    already-approved template/body as given."""
    if not settings.twilio_configured or not settings.twilio_whatsapp_from:
        raise MessagingNotConfiguredError("Twilio WhatsApp is not configured")
    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={
            "To": f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
            "From": settings.twilio_whatsapp_from,
            "Body": body,
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()["sid"]


def send_email(to_address: str, subject: str, body: str) -> None:
    if not settings.smtp_configured:
        raise MessagingNotConfiguredError("SMTP is not configured")

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = to_address

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_from_address, [to_address], message.as_string())
