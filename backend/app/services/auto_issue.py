"""FR-DOC-04: fire active AutoIssueRule rows when order/payment events occur."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.document import AutoIssueRule, Document, DocumentTemplatePreference, DocumentType
from app.models.order import Order
from app.models.shop import Shop
from app.services.pdf_documents import render_document_pdf

logger = logging.getLogger(__name__)

STATUS_TO_TRIGGER = {
    "confirmed": "order_confirmed",
    "packed": "order_packed",
    "delivered": "order_delivered",
    "shipped": "order_packed",
}


def issue_for_order(
    db: Session,
    *,
    shop_id: uuid.UUID,
    order_id: uuid.UUID,
    document_type: DocumentType,
) -> Document | None:
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id, Order.shop_id == shop_id)
        .first()
    )
    if order is None:
        return None

    pref = (
        db.query(DocumentTemplatePreference)
        .filter(
            DocumentTemplatePreference.shop_id == shop_id,
            DocumentTemplatePreference.document_type == document_type,
        )
        .first()
    )
    shop = db.get(Shop, shop_id)
    doc_number = f"{document_type.value.upper()}-{datetime.now(timezone.utc):%Y%m}-{str(order.id)[:8]}"
    document = Document(
        shop_id=shop_id,
        order_id=order.id,
        type=document_type,
        template_id=pref.template_id if pref else "classic",
        document_number=doc_number,
    )
    db.add(document)
    db.flush()
    try:
        pdf_path = render_document_pdf(
            document,
            order,
            shop_name=shop.name if shop else "Shop",
            currency=shop.currency if shop else "BDT",
        )
        document.pdf_ref = pdf_path
    except Exception:
        logger.exception("auto-issue PDF render failed for %s", document_type)
    db.add(document)
    return document


def run_auto_issue(db: Session, shop_id: uuid.UUID, trigger: str, order_id: uuid.UUID) -> list[Document]:
    rules = (
        db.query(AutoIssueRule)
        .filter(
            AutoIssueRule.shop_id == shop_id,
            AutoIssueRule.trigger == trigger,
            AutoIssueRule.is_active.is_(True),
        )
        .all()
    )
    issued: list[Document] = []
    for rule in rules:
        doc = issue_for_order(db, shop_id=shop_id, order_id=order_id, document_type=rule.document_type)
        if doc:
            issued.append(doc)
    return issued
