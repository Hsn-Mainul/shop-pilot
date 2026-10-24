import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.delivery import ParcelStatus


class ParcelBookRequest(BaseModel):
    order_ids: list[uuid.UUID]
    courier: str


class ParcelOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    courier: str
    status: ParcelStatus
    cod_amount: Decimal
    tracking_id: str | None
    area: str | None
    cod_remitted: bool

    model_config = {"from_attributes": True}


class ParcelStatusUpdate(BaseModel):
    status: ParcelStatus
