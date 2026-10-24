import uuid
from datetime import date

from pydantic import BaseModel

from app.models.team_ops import DataHygieneIssueType, LeaveStatus


class ShiftOut(BaseModel):
    id: uuid.UUID
    team_member_id: uuid.UUID
    shift_date: date
    planned_hours: int
    is_confirmed: bool

    model_config = {"from_attributes": True}


class ShiftConfirmRequest(BaseModel):
    is_confirmed: bool = True


class LeaveRequestCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveRequestOut(LeaveRequestCreate):
    id: uuid.UUID
    team_member_id: uuid.UUID
    status: LeaveStatus

    model_config = {"from_attributes": True}


class LeaveStatusUpdate(BaseModel):
    status: LeaveStatus


class DataHygieneIssueOut(BaseModel):
    id: uuid.UUID
    issue_type: DataHygieneIssueType
    related_id: uuid.UUID
    is_resolved: bool

    model_config = {"from_attributes": True}
