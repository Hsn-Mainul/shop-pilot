"""Text-to-speech for live AI voice calls (FR-CALL / FR-VPER).

Uses an OpenAI-compatible `/audio/speech` endpoint when configured.
Callers that need Twilio-native speech can fall back to TwiML <Say>.
"""
from pathlib import Path

import httpx

from app.core.config import settings

STORAGE = Path(__file__).resolve().parents[2] / "storage" / "tts"


class TTSNotConfiguredError(RuntimeError):
    pass


# Map persona voice_name → OpenAI voice id (fallback alloy).
VOICE_MAP = {
    "default_bn_female": "nova",
    "default_bn_male": "onyx",
    "friendly": "nova",
    "professional": "alloy",
}


def synthesize_to_file(text: str, *, voice_name: str = "default_bn_female") -> Path:
    if not settings.llm_api_key:
        raise TTSNotConfiguredError("No LLM/TTS API key configured (settings.llm_api_key)")

    STORAGE.mkdir(parents=True, exist_ok=True)
    voice = VOICE_MAP.get(voice_name, "nova")
    out = STORAGE / f"tts_{abs(hash(text + voice)) % 10_000_000}.mp3"

    if out.is_file() and out.stat().st_size > 0:
        return out

    response = httpx.post(
        f"{settings.llm_base_url}/audio/speech",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={"model": "tts-1", "voice": voice, "input": text[:4000]},
        timeout=60.0,
    )
    response.raise_for_status()
    out.write_bytes(response.content)
    return out
