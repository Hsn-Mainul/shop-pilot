"""Ops readiness — which provider credentials are configured (no secrets returned)."""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/providers")
def provider_status() -> dict:
    """Shows which external providers are ready. Safe to expose to admins — no secrets."""
    return {
        "public_base_url": settings.public_base_url,
        "providers": {
            "database": {"configured": bool(settings.database_url), "label": "PostgreSQL"},
            "redis": {"configured": bool(settings.redis_url), "label": "Redis (realtime + Celery)"},
            "llm": {
                "configured": settings.llm_configured,
                "label": (
                    f"Ollama Local AI ({settings.ollama_chat_model})"
                    if settings.is_ollama
                    else f"Cloud LLM ({settings.llm_model})"
                ),
                "provider": settings.llm_provider,
                "model": settings.ollama_chat_model if settings.is_ollama else settings.llm_model,
                "embed_model": settings.ollama_embed_model,
            },
            "asr": {"configured": settings.asr_configured, "label": "Speech-to-text (Whisper)"},
            "twilio": {
                "configured": settings.twilio_configured and bool(settings.twilio_from_number),
                "label": "Twilio voice / SMS",
                "voice_webhook": bool(settings.twilio_voice_webhook_url) or bool(settings.public_base_url),
            },
            "smtp": {"configured": settings.smtp_configured, "label": "Email (SMTP invites/campaigns)"},
            "meta": {
                "configured": settings.meta_configured and bool(settings.meta_oauth_redirect_uri),
                "label": "Meta Facebook / Instagram OAuth",
            },
            "google_oauth": {
                "configured": bool(settings.google_client_id and settings.google_client_secret),
                "label": "Google OAuth",
            },
            "stripe_oauth": {
                "configured": bool(settings.stripe_client_id and settings.stripe_client_secret),
                "label": "Stripe Connect OAuth",
            },
        },
        "demo_login": {"email": "owner@demo-shop.test", "password": "ChangeMe123!"},
        "note": "Unset providers degrade gracefully; core shop flows work without them.",
    }
