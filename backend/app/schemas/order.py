import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    variant_id: uuid.UUID | None = None
    name_snapshot: str
    quantity: int = 1
    unit_price: Decimal


class OrderItemOut(OrderItemCreate):
    id: uuid.UUID
    unit_cost_snapshot: Decimal | None = None

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    source_channel: str | None = "manual"
    items: list[OrderItemCreate] = Field(default_factory=list)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    invoice_number: str | None = None
    status: OrderStatus
    source_channel: str | None
    total_amount: Decimal
    items: list[OrderItemOut] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrderImportItem(BaseModel):
    customer_phone: str | None = None
    customer_name: str | None = None
    item_name: str
    quantity: int = 1
    unit_price: Decimal
    source_channel: str = "spreadsheet"


class OrderImportRequest(BaseModel):
    rows: list[OrderImportItem]


class OrderImportResult(BaseModel):
    created: int
    order_ids: list[uuid.UUID]
