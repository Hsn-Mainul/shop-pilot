from datetime import time

from pydantic import BaseModel, Field


class VoicePersonaUpdate(BaseModel):
    voice_name: str | None = None
    tone: str | None = None
    speaking_pace: str | None = None
    opening_script: str | None = None
    must_confirm_before_order: bool | None = None
    forbidden_topics: list[str] | None = None


class VoicePersonaOut(BaseModel):
    voice_name: str
    tone: str
    speaking_pace: str
    opening_script: str | None
    must_confirm_before_order: bool
    forbidden_topics: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CallRoutingRuleUpdate(BaseModel):
    business_hours_start: time | None = None
    business_hours_end: time | None = None
    overflow_action: str | None = None
    prioritize_repeat_customers: bool | None = None
    max_concurrent_human_lines: int | None = None


class CallRoutingRuleOut(BaseModel):
    business_hours_start: time | None
    business_hours_end: time | None
    overflow_action: str
    prioritize_repeat_customers: bool
    max_concurrent_human_lines: int

    model_config = {"from_attributes": True}


class SimulateChatRequest(BaseModel):
    message: str


class SimulateChatResponse(BaseModel):
    reply: str
    note: str = "Uses the real LLM when configured (settings.llm_api_key); falls back to a keyword match otherwise."


class SimulateCallRequest(BaseModel):
    dialect_code: str | None = None
    opening_message: str | None = None


class SimulateCallResponse(BaseModel):
    transcript_preview: str
    dialect_used: str
    tts_ready: bool = False
    note: str = "Uses Voice Persona opening script; live calls use /calls/twiml + TTS when configured."
