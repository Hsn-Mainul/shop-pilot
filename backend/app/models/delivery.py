import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ParcelStatus(str, enum.Enum):
    TO_BOOK = "to_book"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    ON_HOLD = "on_hold"


class DeliveryParcel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "delivery_parcels"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    courier: Mapped[str] = mapped_column(String(50))
    status: Mapped[ParcelStatus] = mapped_column(Enum(ParcelStatus), default=ParcelStatus.TO_BOOK, index=True)
    cod_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tracking_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cod_remitted: Mapped[bool] = mapped_column(default=False)

    order: Mapped["Order"] = relationship()
