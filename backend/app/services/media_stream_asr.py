"""Twilio Media Streams → dialect-aware ASR loop (FR-CALL-05/06).

Buffers inbound μ-law frames, periodically flushes a WAV chunk, runs ASR with
the call's dialect pack, appends to CallSession.transcript, and broadcasts.
"""
from __future__ import annotations

try:
    import audioop  # stdlib through 3.12
except ModuleNotFoundError:  # Python 3.13+ removed audioop
    import audioop_lts as audioop  # type: ignore

import base64
import json
import logging
import tempfile
import uuid
import wave
from pathlib import Path

from app.db.session import SessionLocal
from app.integrations.asr import ASRNotConfiguredError, transcribe_audio_file
from app.models.call import CallSession, CallStatus
from app.models.integration import DialectPack, ShopDialectPreference
from app.realtime.hub import hub

logger = logging.getLogger(__name__)

# Flush ~2s of 8kHz μ-law (1 byte/sample) ≈ 16000 bytes
FLUSH_BYTES = 16_000


def _mulaw_b64_to_pcm(payload_b64: str) -> bytes:
    mulaw = base64.b64decode(payload_b64)
    return audioop.ulaw2lin(mulaw, 2)  # 16-bit linear PCM


def _write_wav(pcm: bytes, path: Path, sample_rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


def _dialect_code_for_call(db, call: CallSession) -> str | None:
    if call.dialect_pack_id:
        pack = db.get(DialectPack, call.dialect_pack_id)
        return pack.language_code if pack else None
    pref = (
        db.query(ShopDialectPreference)
        .filter(ShopDialectPreference.shop_id == call.shop_id, ShopDialectPreference.is_enabled.is_(True))
        .first()
    )
    if pref:
        pack = db.get(DialectPack, pref.dialect_pack_id)
        return pack.language_code if pack else None
    return "bn-STD"


def _append_transcript(call_id: uuid.UUID, text: str, confidence: float, dialect: str | None) -> None:
    db = SessionLocal()
    try:
        call = db.get(CallSession, call_id)
        if call is None:
            return
        line = f"\n[stream ASR {dialect or '?'} conf={confidence:.2f}] Caller: {text}"
        call.transcript = (call.transcript or "") + line

        # Optional AI reply into transcript (same knowledge path as TwiML gather)
        try:
            from app.api.v1.endpoints.ai import _answer_from_shop_knowledge
            from app.models.shop import Shop
            from app.services.ai_credits import consume_voice_minutes, module_enabled

            shop = db.get(Shop, call.shop_id)
            if shop and call.handled_by_ai and module_enabled(shop, "voice", True):
                if consume_voice_minutes(db, call.shop_id, minutes=0.5, reason="stream_asr_reply"):
                    reply = _answer_from_shop_knowledge(db, shop, text)
                    if shop.name.lower() not in reply.lower():
                        reply = f"{reply} — {shop.name}"
                    call.transcript += f"\nAI: {reply}"
                else:
                    call.transcript += "\nAI: [voice credits exhausted]"
        except Exception:
            logger.debug("AI reply on stream skipped", exc_info=True)

        call.status = CallStatus.IN_PROGRESS
        db.add(call)
        db.commit()
        hub.broadcast_sync(
            call.shop_id,
            "call.transcript",
            {
                "call_id": str(call.id),
                "text": text,
                "confidence": confidence,
                "dialect": dialect,
                "transcript": call.transcript,
            },
        )
    finally:
        db.close()


class MediaStreamSession:
    """Per-call buffer + flush state for one Twilio Media Stream connection."""

    def __init__(self, call_id: uuid.UUID) -> None:
        self.call_id = call_id
        self.pcm_buf = bytearray()
        self.dialect_code: str | None = None
        self._load_dialect()

    def _load_dialect(self) -> None:
        db = SessionLocal()
        try:
            call = db.get(CallSession, self.call_id)
            if call:
                self.dialect_code = _dialect_code_for_call(db, call)
                if call.dialect_pack_id is None and self.dialect_code:
                    pack = (
                        db.query(DialectPack)
                        .filter(DialectPack.language_code == self.dialect_code)
                        .first()
                    )
                    if pack:
                        call.dialect_pack_id = pack.id
                        db.add(call)
                        db.commit()
        finally:
            db.close()

    def on_media_payload(self, payload_b64: str) -> None:
        try:
            self.pcm_buf.extend(_mulaw_b64_to_pcm(payload_b64))
        except Exception:
            logger.debug("bad media payload", exc_info=True)
            return
        if len(self.pcm_buf) >= FLUSH_BYTES:
            self.flush()

    def flush(self) -> None:
        if len(self.pcm_buf) < 3200:  # <~0.2s — skip
            self.pcm_buf.clear()
            return
        pcm = bytes(self.pcm_buf)
        self.pcm_buf.clear()
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                path = Path(tmp.name)
            _write_wav(pcm, path)
            text, confidence = transcribe_audio_file(str(path), dialect_code=self.dialect_code)
            path.unlink(missing_ok=True)
            if text and text.strip():
                _append_transcript(self.call_id, text.strip(), confidence, self.dialect_code)
        except ASRNotConfiguredError:
            logger.debug("ASR not configured — stream frames buffered but not transcribed")
        except Exception:
            logger.exception("stream ASR flush failed for %s", self.call_id)

    def handle_message(self, raw: str) -> bool:
        """Process one Twilio JSON message. Returns False when stream should stop."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return True
        event = data.get("event")
        if event == "media":
            payload = (data.get("media") or {}).get("payload")
            if payload:
                self.on_media_payload(payload)
        elif event == "stop":
            self.flush()
            return False
        elif event == "start":
            # Could read customParameters for dialect override
            params = (data.get("start") or {}).get("customParameters") or {}
            if params.get("dialect"):
                self.dialect_code = params["dialect"]
        return True
