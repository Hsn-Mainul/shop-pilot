"""Real PDF generation for invoices/receipts/etc. (FR-DOC-01/02).

This renders a plain, single "Classic" layout with reportlab — good enough to
produce a genuine, openable PDF per document. The template *gallery* (multiple
visual designs to choose from) is a frontend/asset concern layered on top of
this; swapping in a different layout later means adding another function here
and selecting it by `template_id`, not changing the calling code.
"""
import os
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.document import Document, DocumentType
from app.models.order import Order

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "documents")
os.makedirs(STORAGE_DIR, exist_ok=True)

_TYPE_TITLES = {
    DocumentType.INVOICE: "INVOICE",
    DocumentType.MONEY_RECEIPT: "MONEY RECEIPT",
    DocumentType.QUOTATION: "QUOTATION",
    DocumentType.CREDIT_NOTE: "CREDIT NOTE",
    DocumentType.DELIVERY_CHALLAN: "DELIVERY CHALLAN",
    DocumentType.PACKING_SLIP: "PACKING SLIP",
    DocumentType.VAT_INVOICE: "VAT INVOICE (MUSHAK-6.3)",
}


def render_document_pdf(document: Document, order: Order, shop_name: str, currency: str) -> str:
    """Render `document` to a PDF file on local storage and return its path."""
    file_path = os.path.join(STORAGE_DIR, f"{document.id}.pdf")
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, shop_name)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 20 * mm, y, _TYPE_TITLES.get(document.type, document.type.value.upper()))

    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Document No: {document.document_number}")
    c.drawRightString(width - 20 * mm, y, f"Date: {document.created_at:%Y-%m-%d}")

    y -= 8 * mm
    c.drawString(20 * mm, y, f"Order: {order.id}")
    c.drawString(width / 2, y, f"Status: {order.status.value}")

    y -= 12 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Item")
    c.drawString(110 * mm, y, "Qty")
    c.drawString(130 * mm, y, "Unit Price")
    c.drawString(160 * mm, y, "Line Total")
    y -= 4 * mm
    c.line(20 * mm, y, width - 20 * mm, y)

    c.setFont("Helvetica", 10)
    for item in order.items:
        y -= 7 * mm
        line_total = Decimal(item.quantity) * item.unit_price
        c.drawString(20 * mm, y, item.name_snapshot[:50])
        c.drawString(110 * mm, y, str(item.quantity))
        c.drawString(130 * mm, y, f"{currency} {item.unit_price}")
        c.drawString(160 * mm, y, f"{currency} {line_total}")

    y -= 10 * mm
    c.line(20 * mm, y, width - 20 * mm, y)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 20 * mm, y, f"Total: {currency} {order.total_amount}")

    c.showPage()
    c.save()
    return file_path
