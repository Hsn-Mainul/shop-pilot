import uuid

from pydantic import BaseModel


class SavedReplyCreate(BaseModel):
    shortcut: str
    title: str
    body: str
    language: str = "en"


class SavedReplyUpdate(BaseModel):
    shortcut: str | None = None
    title: str | None = None
    body: str | None = None
    language: str | None = None


class SavedReplyOut(SavedReplyCreate):
    id: uuid.UUID
    usage_count: int

    model_config = {"from_attributes": True}
