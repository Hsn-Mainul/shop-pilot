import uuid

from pydantic import BaseModel


class CustomerBase(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    segment: str | None = None
    is_blocked: bool | None = None


class CustomerOut(CustomerBase):
    id: uuid.UUID
    segment: str | None = None
    is_blocked: bool

    model_config = {"from_attributes": True}
