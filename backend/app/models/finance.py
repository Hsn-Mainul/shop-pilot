import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ExpenseCategory(str, enum.Enum):
    INVENTORY_PURCHASE = "inventory_purchase"
    RENT = "rent"
    SALARIES = "salaries"
    DELIVERY_COURIER = "delivery_courier"
    MARKETING = "marketing"
    UTILITIES = "utilities"
    PAYMENT_GATEWAY_FEES = "payment_gateway_fees"
    TELEPHONY = "telephony"
    OTHER = "other"


class LedgerAccountType(str, enum.Enum):
    CASH = "cash"
    BANK = "bank"
    WALLET = "wallet"
    STOCK_VALUE = "stock_value"


class Expense(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    category: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    paid_from: Mapped[str] = mapped_column(String(30))  # cash, bkash, nagad, bank, card
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class LedgerEntry(UUIDMixin, TimestampMixin, Base):
    """Derived bookkeeping posting used to compute P&L and net worth."""

    __tablename__ = "ledger_entries"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    account_type: Mapped[LedgerAccountType] = mapped_column(Enum(LedgerAccountType))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))  # positive = money in, negative = money out
    ref_type: Mapped[str] = mapped_column(String(30))  # order, payment, expense, stock_adjustment
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
