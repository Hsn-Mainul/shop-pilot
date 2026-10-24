import uuid

from pydantic import BaseModel

from app.models.call import CallDirection, CallStatus


class OutboundCallRequest(BaseModel):
    customer_id: uuid.UUID
    script_note: str | None = None


class CallSessionOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    direction: CallDirection
    status: CallStatus
    duration_seconds: int
    recording_ref: str | None
    transcript: str | None
    handled_by_ai: bool

    model_config = {"from_attributes": True}


class CallHandoverRequest(BaseModel):
    team_member_id: uuid.UUID
