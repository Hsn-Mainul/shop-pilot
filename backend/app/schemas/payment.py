import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    order_id: uuid.UUID
    method: PaymentMethod
    amount: Decimal
    sender_number: str | None = None
    trx_ref: str | None = None
    note: str | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    method: PaymentMethod
    amount: Decimal
    sender_number: str | None
    trx_ref: str | None
    status: PaymentStatus
    note: str | None

    model_config = {"from_attributes": True}
