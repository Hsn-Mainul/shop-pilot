import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class DocumentType(str, enum.Enum):
    INVOICE = "invoice"
    MONEY_RECEIPT = "money_receipt"
    QUOTATION = "quotation"
    CREDIT_NOTE = "credit_note"
    DELIVERY_CHALLAN = "delivery_challan"
    PACKING_SLIP = "packing_slip"
    VAT_INVOICE = "vat_invoice"


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))
    template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_number: Mapped[str] = mapped_column(String(50))
    pdf_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order: Mapped["Order"] = relationship()


class DocumentTemplatePreference(UUIDMixin, TimestampMixin, Base):
    """Which template is the default per document type, per shop."""

    __tablename__ = "document_template_preferences"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))
    template_id: Mapped[str] = mapped_column(String(100))


class AutoIssueRule(UUIDMixin, TimestampMixin, Base):
    """Toggle: e.g. invoice-on-confirmation, receipt-per-payment, etc. (FR-DOC-04)."""

    __tablename__ = "auto_issue_rules"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(100))  # order_confirmed, payment_recorded, order_delivered, order_packed
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))
    is_active: Mapped[bool] = mapped_column(default=True)
