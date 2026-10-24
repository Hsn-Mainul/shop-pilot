import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductVariantBase(BaseModel):
    sku: str | None = None
    attributes: dict = Field(default_factory=dict)
    stock_qty: int = 0
    reorder_point: int = 0
    batch_code: str | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    location: str | None = None


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantOut(ProductVariantBase):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str
    page_id: str | None = None
    category: str | None = None
    description: str | None = None
    price: Decimal
    cost: Decimal | None = None
    photo_url: str | None = None
    kind: str = "product"  # product | service
    pricing_mode: str = "fixed"  # fixed | from | on_quote
    scheduling: dict = Field(default_factory=dict)
    track_serial: bool = False
    track_batch: bool = False


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = None
    page_id: str | None = None
    category: str | None = None
    description: str | None = None
    price: Decimal | None = None
    cost: Decimal | None = None
    photo_url: str | None = None
    kind: str | None = None
    pricing_mode: str | None = None
    scheduling: dict | None = None
    track_serial: bool | None = None
    track_batch: bool | None = None


class ProductOut(ProductBase):
    id: uuid.UUID
    variants: list[ProductVariantOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StockAdjustRequest(BaseModel):
    variant_id: uuid.UUID
    delta_qty: int
    reason: str = "stock_count"
    note: str | None = None
    batch_code: str | None = None
    serial_numbers: list[str] | None = None


class StockLedgerOut(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    delta_qty: int
    reason: str
    order_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    note: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class BulkProductImportItem(BaseModel):
    name: str
    price: Decimal
    category: str | None = None
    cost: Decimal | None = None
    stock_qty: int = 0
    kind: str = "product"
    pricing_mode: str = "fixed"
    sku: str | None = None


class BulkProductImportRequest(BaseModel):
    items: list[BulkProductImportItem]


class BulkProductImportResult(BaseModel):
    created: int
    product_ids: list[uuid.UUID]
