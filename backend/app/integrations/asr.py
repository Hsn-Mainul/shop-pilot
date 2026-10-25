"""Real speech-to-text for voice notes and call transcripts (FR-VOICE-01/02, FR-CALL-05/06).

Dialect packs map to Whisper `language` + a prompt hint. Beta dialects get a
lower confidence estimate until a dedicated regional model is available.
"""
import httpx

from app.core.config import settings

# language_code → (ISO-639-1 for Whisper, prompt hint, base confidence)
DIALECT_ASR_PROFILE: dict[str, tuple[str, str, float]] = {
    "bn-STD": ("bn", "Standard Bangla retail conversation.", 0.85),
    "bn-SYL": ("bn", "Sylheti Bangla dialect, informal shop talk.", 0.65),
    "bn-CTG": ("bn", "Chittagonian Bangla dialect, informal shop talk.", 0.62),
    "bn-RAJ": ("bn", "Rajshahi / North Bengal Bangla dialect.", 0.68),
    "bn-KHU": ("bn", "Khulna / South-West Bangla dialect.", 0.66),
    "bn-BAR": ("bn", "Barisal Bangla dialect.", 0.64),
    "bn-MYM": ("bn", "Mymensingh Bangla dialect.", 0.67),
    "en": ("en", "English retail conversation.", 0.9),
    "hi": ("hi", "Hindi retail conversation.", 0.85),
    "ur": ("ur", "Urdu retail conversation.", 0.72),
}


class ASRNotConfiguredError(RuntimeError):
    pass


def resolve_dialect_profile(language_code: str | None) -> tuple[str | None, str | None, float]:
    if not language_code:
        return None, None, 0.75
    profile = DIALECT_ASR_PROFILE.get(language_code)
    if profile:
        return profile
    # Unknown pack: treat primary tag as language (bn-XXX → bn)
    primary = language_code.split("-")[0].lower()
    return primary, f"Dialect code {language_code}.", 0.55


def transcribe_audio_file(
    file_path: str,
    *,
    language_hint: str | None = None,
    dialect_code: str | None = None,
) -> tuple[str, float]:
    """Returns (transcript_text, confidence_estimate)."""
    if not settings.asr_configured:
        raise ASRNotConfiguredError(
            "No ASR API key configured — set ASR_API_KEY, or configure GROQ_API_KEY which this falls back to"
        )

    lang, prompt, confidence = resolve_dialect_profile(dialect_code)
    if language_hint and not lang:
        lang = language_hint

    data: dict[str, str] = {"model": settings.effective_asr_model}
    if lang:
        data["language"] = lang
    if prompt:
        data["prompt"] = prompt

    with open(file_path, "rb") as f:
        response = httpx.post(
            f"{settings.effective_asr_base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.effective_asr_api_key}"},
            data=data,
            files={"file": f},
            timeout=60.0,
        )
    response.raise_for_status()
    body = response.json()
    return body["text"], confidence
