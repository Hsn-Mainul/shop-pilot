import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURNED = "returned"
    ON_HOLD = "on_hold"


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW, index=True)
    source_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)  # chat, call, manual, website
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    # Set when this order was placed automatically by the AI from a chat conversation
    # (see app/services/chat_order_service.py) — also used to stop a second confirmed
    # order being created from the same conversation.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True
    )
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Human-facing reference the customer uses to track shipment, e.g. "INV-000042".
    # Separate from `id` because that's an internal UUID, not something to read out.
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)

    shop: Mapped["Shop"] = relationship(back_populates="orders")
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")


class OrderItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )
    name_snapshot: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    unit_cost_snapshot: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
