import uuid
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.db.session import get_db
from app.integrations.telephony import TelephonyNotConfiguredError, place_call
from app.integrations.tts import TTSNotConfiguredError, synthesize_to_file
from app.models.call import CallDirection, CallSession, CallStatus
from app.models.customer import Customer
from app.models.shop import Shop
from app.models.team_member import TeamMember, TeamRole
from app.models.voice_config import CallRoutingRule, VoicePersona
from app.realtime.hub import hub
from app.schemas.call import CallHandoverRequest, CallSessionOut, OutboundCallRequest
from app.schemas.voice_config import (
    CallRoutingRuleOut,
    CallRoutingRuleUpdate,
    VoicePersonaOut,
    VoicePersonaUpdate,
)

router = APIRouter(prefix="/calls", tags=["calls"])


def _twiml_url_for_call(call_id: uuid.UUID) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/api/v1/calls/twiml?call_id={call_id}"


def _status_callback_url(call_id: uuid.UUID) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/api/v1/calls/{call_id}/telephony-status"


def _build_say_twiml(text: str, *, gather_action: str | None = None, voice: str = "Polly.Aditi") -> str:
    safe = escape(text)
    if gather_action:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Gather input="speech" action="{escape(gather_action)}" '
            f'timeout="4" speechTimeout="auto"><Say voice="{escape(voice)}">{safe}</Say></Gather>'
            f'<Say voice="{escape(voice)}">I did not catch that. Goodbye.</Say></Response>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Say voice="{escape(voice)}">{safe}</Say><Hangup/></Response>'
    )


@router.get("", response_model=list[CallSessionOut])
def list_calls(
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CallSessionOut]:
    return (
        db.query(CallSession)
        .filter(CallSession.shop_id == current_user.shop_id)
        .order_by(CallSession.created_at.desc())
        .limit(100)
        .all()
    )


@router.post("/outbound", response_model=CallSessionOut, status_code=status.HTTP_201_CREATED)
def place_outbound_call(
    payload: OutboundCallRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> CallSessionOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.shop_id == current_user.shop_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    call = CallSession(
        shop_id=current_user.shop_id,
        customer_id=customer.id,
        direction=CallDirection.OUTBOUND,
        status=CallStatus.RINGING,
        handled_by_ai=True,
        transcript=payload.script_note,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    if customer.phone and settings.twilio_configured:
        try:
            # Prefer media-stream TwiML when ASR is configured (dialect live transcript);
            # otherwise classic Gather/Say opening script.
            base = settings.public_base_url.rstrip("/")
            twiml = (
                f"{base}/api/v1/calls/twiml/stream?call_id={call.id}"
                if settings.asr_configured
                else _twiml_url_for_call(call.id)
            )
            sid = place_call(
                customer.phone,
                twiml_url=twiml,
                status_callback=_status_callback_url(call.id),
            )
            call.recording_ref = sid  # reuse field to store provider call SID
            db.add(call)
            db.commit()
            db.refresh(call)
        except TelephonyNotConfiguredError:
            pass
        except Exception:
            call.status = CallStatus.MISSED
            db.add(call)
            db.commit()
            db.refresh(call)

    hub.broadcast_sync(current_user.shop_id, "call.updated", {"call_id": str(call.id)})
    return call


@router.post("/twiml")
async def twiml_entry(call_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Twilio fetches this when the call connects — speak persona opening script (FR-VPER)."""
    call = db.get(CallSession, call_id)
    if call is None:
        return Response(
            content=_build_say_twiml("Sorry, this call could not be connected."),
            media_type="application/xml",
        )

    persona = db.query(VoicePersona).filter(VoicePersona.shop_id == call.shop_id).first()
    shop = db.get(Shop, call.shop_id)
    shop_name = shop.name if shop else "our shop"
    opening = (
        (call.transcript or "").strip()
        or (persona.opening_script if persona and persona.opening_script else None)
        or f"Hello, thank you for calling {shop_name}. How can I help you today?"
    )
    # Enforce brand name in automated speech
    if shop_name.lower() not in opening.lower():
        opening = f"{opening} You are speaking with {shop_name}."

    call.status = CallStatus.IN_PROGRESS
    call.transcript = opening
    db.add(call)
    db.commit()
    hub.broadcast_sync(call.shop_id, "call.updated", {"call_id": str(call.id), "status": "in_progress"})

    gather = f"{settings.public_base_url.rstrip('/')}/api/v1/calls/twiml/gather?call_id={call_id}"

    # Prefer pre-rendered TTS audio when LLM key is present; else Twilio <Say>.
    if persona and settings.llm_api_key:
        try:
            path = synthesize_to_file(opening, voice_name=persona.voice_name)
            audio_url = f"{settings.public_base_url.rstrip('/')}/api/v1/calls/tts-audio/{path.name}"
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<Response><Gather input="speech" action="{escape(gather)}" '
                f'timeout="4" speechTimeout="auto"><Play>{escape(audio_url)}</Play></Gather>'
                "<Say>I did not catch that. Goodbye.</Say></Response>"
            )
            return Response(content=xml, media_type="application/xml")
        except TTSNotConfiguredError:
            pass

    return Response(content=_build_say_twiml(opening, gather_action=gather), media_type="application/xml")


@router.post("/twiml/gather")
async def twiml_gather(
    call_id: uuid.UUID,
    speech_result: str | None = Form(default=None, alias="SpeechResult"),
    db: Session = Depends(get_db),
) -> Response:
    """Handle caller speech, answer from shop knowledge / LLM, continue dialog."""
    from app.api.v1.endpoints.ai import _answer_from_shop_knowledge
    from app.services.ai_credits import consume_voice_minutes, module_enabled

    call = db.get(CallSession, call_id)
    if call is None:
        return Response(content=_build_say_twiml("Goodbye."), media_type="application/xml")

    shop = db.get(Shop, call.shop_id)
    heard = (speech_result or "").strip()
    if heard:
        call.transcript = (call.transcript or "") + f"\nCaller: {heard}"
        reply = "Thank you."
        if shop and module_enabled(shop, "voice", True):
            if consume_voice_minutes(db, call.shop_id, minutes=0.5, reason="twiml_gather_reply"):
                reply = _answer_from_shop_knowledge(db, shop, heard)
                if shop.name.lower() not in reply.lower():
                    reply = f"{reply} — {shop.name}"
            else:
                reply = "I'm sorry, our voice assistant is temporarily unavailable. Please try again later."
        elif shop:
            reply = "Voice AI is turned off for this shop. A teammate will call you back."
        call.transcript += f"\nAI: {reply}"
        db.add(call)
        db.commit()
        hub.broadcast_sync(call.shop_id, "call.updated", {"call_id": str(call.id)})
        gather = f"{settings.public_base_url.rstrip('/')}/api/v1/calls/twiml/gather?call_id={call_id}"
        return Response(content=_build_say_twiml(reply, gather_action=gather), media_type="application/xml")

    call.status = CallStatus.COMPLETED
    db.add(call)
    db.commit()
    return Response(content=_build_say_twiml("Thank you for calling. Goodbye."), media_type="application/xml")


@router.post("/{call_id}/telephony-status")
async def telephony_status(
    call_id: uuid.UUID,
    call_status: str | None = Form(default=None, alias="CallStatus"),
    call_duration: str | None = Form(default=None, alias="CallDuration"),
    db: Session = Depends(get_db),
) -> dict:
    call = db.get(CallSession, call_id)
    if call is None:
        return {"ok": False}
    status_map = {
        "queued": CallStatus.RINGING,
        "ringing": CallStatus.RINGING,
        "in-progress": CallStatus.IN_PROGRESS,
        "completed": CallStatus.COMPLETED,
        "busy": CallStatus.MISSED,
        "failed": CallStatus.MISSED,
        "no-answer": CallStatus.MISSED,
        "canceled": CallStatus.MISSED,
    }
    if call_status and call_status.lower() in status_map:
        call.status = status_map[call_status.lower()]
    if call_duration and call_duration.isdigit():
        call.duration_seconds = int(call_duration)
    db.add(call)
    db.commit()
    hub.broadcast_sync(call.shop_id, "call.updated", {"call_id": str(call.id), "status": call_status})
    return {"ok": True}


@router.get("/tts-audio/{filename}")
def serve_tts_audio(filename: str) -> Response:
    from pathlib import Path

    from fastapi.responses import FileResponse

    from app.integrations.tts import STORAGE

    safe = Path(filename).name
    path = STORAGE / safe
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/config/voice-persona", response_model=VoicePersonaOut)
def get_voice_persona(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)), db: Session = Depends(get_db)
) -> VoicePersonaOut:
    persona = db.query(VoicePersona).filter(VoicePersona.shop_id == current_user.shop_id).first()
    if persona is None:
        persona = VoicePersona(shop_id=current_user.shop_id)
        db.add(persona)
        db.commit()
        db.refresh(persona)
    return persona


@router.patch("/config/voice-persona", response_model=VoicePersonaOut)
def update_voice_persona(
    payload: VoicePersonaUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> VoicePersonaOut:
    persona = db.query(VoicePersona).filter(VoicePersona.shop_id == current_user.shop_id).first()
    if persona is None:
        persona = VoicePersona(shop_id=current_user.shop_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(persona, field, value)
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


@router.get("/config/routing-rules", response_model=CallRoutingRuleOut)
def get_call_routing_rules(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)), db: Session = Depends(get_db)
) -> CallRoutingRuleOut:
    rule = db.query(CallRoutingRule).filter(CallRoutingRule.shop_id == current_user.shop_id).first()
    if rule is None:
        rule = CallRoutingRule(shop_id=current_user.shop_id)
        db.add(rule)
        db.commit()
        db.refresh(rule)
    return rule


@router.patch("/config/routing-rules", response_model=CallRoutingRuleOut)
def update_call_routing_rules(
    payload: CallRoutingRuleUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> CallRoutingRuleOut:
    rule = db.query(CallRoutingRule).filter(CallRoutingRule.shop_id == current_user.shop_id).first()
    if rule is None:
        rule = CallRoutingRule(shop_id=current_user.shop_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/config/metrics")
def call_quality_metrics(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """FR-VPER-04: voice-specific quality metrics."""
    calls = db.query(CallSession).filter(CallSession.shop_id == current_user.shop_id).all()
    total = len(calls)
    if total == 0:
        return {
            "total_calls": 0,
            "average_handling_time_seconds": None,
            "resolved_without_handover_pct": None,
            "calls_by_dialect": {},
        }

    avg_duration = sum((c.duration_seconds or 0) for c in calls) / total
    resolved_without_handover = sum(1 for c in calls if c.handled_by_ai and c.status == CallStatus.COMPLETED)
    by_dialect: dict[str, int] = {}
    for c in calls:
        key = str(c.dialect_pack_id) if c.dialect_pack_id else "unknown"
        by_dialect[key] = by_dialect.get(key, 0) + 1

    return {
        "total_calls": total,
        "average_handling_time_seconds": avg_duration,
        "resolved_without_handover_pct": round(100 * resolved_without_handover / total, 1),
        "calls_by_dialect": by_dialect,
    }


def _get_owned_call(call_id: uuid.UUID, current_user: TeamMember, db: Session) -> CallSession:
    call = (
        db.query(CallSession)
        .filter(CallSession.id == call_id, CallSession.shop_id == current_user.shop_id)
        .first()
    )
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call


@router.get("/{call_id}", response_model=CallSessionOut)
def get_call(
    call_id: uuid.UUID,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CallSessionOut:
    return _get_owned_call(call_id, current_user, db)


@router.post("/{call_id}/handover", response_model=CallSessionOut)
def handover_call(
    call_id: uuid.UUID,
    payload: CallHandoverRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> CallSessionOut:
    call = _get_owned_call(call_id, current_user, db)
    call.status = CallStatus.HANDED_OVER
    call.handed_over_to = payload.team_member_id
    call.handled_by_ai = False
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


@router.post("/{call_id}/monitor", response_model=CallSessionOut)
def monitor_call(
    call_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> CallSessionOut:
    """Authorizes listen-in; returns live transcript + provider call SID for audio."""
    call = _get_owned_call(call_id, current_user, db)
    hub.broadcast_sync(
        current_user.shop_id,
        "call.monitor",
        {"call_id": str(call.id), "status": call.status.value if call.status else None},
    )
    return call


@router.post("/twiml/stream")
async def twiml_media_stream(call_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Bidirectional media stream + opening Say (dialect ASR on /ws/media/{call_id})."""
    call = db.get(CallSession, call_id)
    persona = None
    shop_name = "our shop"
    if call:
        persona = db.query(VoicePersona).filter(VoicePersona.shop_id == call.shop_id).first()
        shop = db.get(Shop, call.shop_id)
        shop_name = shop.name if shop else shop_name
        call.status = CallStatus.IN_PROGRESS
        db.add(call)
        db.commit()

    opening = (
        (call.transcript if call and call.transcript else None)
        or (persona.opening_script if persona and persona.opening_script else None)
        or f"Hello, thank you for calling {shop_name}. How can I help you today?"
    )
    dialect = "bn-STD"
    if call and call.dialect_pack_id:
        from app.models.integration import DialectPack

        pack = db.get(DialectPack, call.dialect_pack_id)
        if pack:
            dialect = pack.language_code

    stream_url = (
        settings.public_base_url.rstrip("/")
        .replace("https://", "wss://")
        .replace("http://", "ws://")
        + f"/ws/media/{call_id}"
    )
    gather = f"{settings.public_base_url.rstrip('/')}/api/v1/calls/twiml/gather?call_id={call_id}"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Start><Stream url="{escape(stream_url)}">'
        f'<Parameter name="dialect" value="{escape(dialect)}" />'
        "</Stream></Start>"
        f'<Gather input="speech" action="{escape(gather)}" timeout="5" speechTimeout="auto">'
        f'<Say voice="Polly.Aditi">{escape(opening)}</Say>'
        "</Gather>"
        '<Say>Thank you for calling. Goodbye.</Say>'
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")
