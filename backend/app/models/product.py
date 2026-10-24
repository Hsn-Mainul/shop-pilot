import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    # Which connected social page this item belongs to (null = shared across all of the shop's pages).
    # Lets a shop running several Facebook/Instagram pages keep each page's own catalog separate,
    # so the AI only quotes products that actually belong to the page a customer is messaging.
    page_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # product | service (FR-CAT services catalogue)
    kind: Mapped[str] = mapped_column(String(20), default="product")
    # fixed | from | on_quote — mainly for services
    pricing_mode: Mapped[str] = mapped_column(String(20), default="fixed")
    # e.g. {"mode": "time_slot"|"due_date", "duration_minutes": 60, "recurrence": "weekly"|null}
    scheduling: Mapped[dict] = mapped_column(JSONB, default=dict)
    track_serial: Mapped[bool] = mapped_column(default=False)
    track_batch: Mapped[bool] = mapped_column(default=False)
    # Dense vector representation of product title, category, description, and variants
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)

    shop: Mapped["Shop"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductVariant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), index=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)  # e.g. {"size": "M", "color": "Red"}
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    batch_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_numbers: Mapped[list] = mapped_column(JSONB, default=list)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")


class StockLedgerEntry(UUIDMixin, TimestampMixin, Base):
    """Append-only audit log for every stock change (FR-CAT-05)."""

    __tablename__ = "stock_ledger_entries"

    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id"), index=True)
    delta_qty: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(100))  # order_confirmed, order_cancelled, stock_count, receive_stock
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("team_members.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
