"""Real outbound-call placement via Twilio's Voice REST API (FR-CALL-01/03)."""
import httpx

from app.core.config import settings


class TelephonyNotConfiguredError(RuntimeError):
    pass


def place_call(
    to_number: str,
    *,
    twiml_url: str | None = None,
    status_callback: str | None = None,
) -> str:
    """Places a real outbound call via Twilio and returns the provider's call SID.

    `twiml_url` (or settings.twilio_voice_webhook_url) must point at a TwiML
    endpoint that tells Twilio what to say once connected.
    """
    if not settings.twilio_configured:
        raise TelephonyNotConfiguredError("Twilio credentials not configured")
    if not settings.twilio_from_number:
        raise TelephonyNotConfiguredError("settings.twilio_from_number is not set")

    url = twiml_url or settings.twilio_voice_webhook_url
    if not url:
        raise TelephonyNotConfiguredError("settings.twilio_voice_webhook_url is not set")

    data: dict[str, str] = {
        "To": to_number,
        "From": settings.twilio_from_number,
        "Url": url,
    }
    if status_callback:
        data["StatusCallback"] = status_callback
        data["StatusCallbackEvent"] = "initiated ringing answered completed"

    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Calls.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data=data,
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()["sid"]
