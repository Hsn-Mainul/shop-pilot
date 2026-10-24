import uuid

from pydantic import BaseModel

from app.models.support import SupportRequestStatus


class SupportRequestCreate(BaseModel):
    subject: str
    body: str


class SupportRequestOut(SupportRequestCreate):
    id: uuid.UUID
    status: SupportRequestStatus

    model_config = {"from_attributes": True}
