import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_role
from app.db.session import get_db
from app.models.document import AutoIssueRule, Document, DocumentTemplatePreference
from app.models.order import Order
from app.models.team_member import TeamMember, TeamRole
from app.schemas.document import (
    AutoIssueRuleCreate,
    AutoIssueRuleOut,
    AutoIssueRuleUpdate,
    DocumentIssueRequest,
    DocumentOut,
    TemplateDefaultUpdate,
)
from app.services.pdf_documents import render_document_pdf

router = APIRouter(tags=["documents"])

DEFAULT_TRIGGERS = [
    ("order_confirmed", "invoice"),
    ("payment_recorded", "money_receipt"),
    ("order_packed", "packing_slip"),
    ("order_delivered", "delivery_challan"),
]


@router.get("/documents/templates")
def list_template_defaults(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    prefs = (
        db.query(DocumentTemplatePreference)
        .filter(DocumentTemplatePreference.shop_id == current_user.shop_id)
        .all()
    )
    return [{"document_type": p.document_type, "template_id": p.template_id} for p in prefs]


@router.patch("/documents/templates/default")
def set_default_template(
    payload: TemplateDefaultUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    pref = (
        db.query(DocumentTemplatePreference)
        .filter(
            DocumentTemplatePreference.shop_id == current_user.shop_id,
            DocumentTemplatePreference.document_type == payload.document_type,
        )
        .first()
    )
    if pref is None:
        pref = DocumentTemplatePreference(shop_id=current_user.shop_id, document_type=payload.document_type, template_id=payload.template_id)
    else:
        pref.template_id = payload.template_id
    db.add(pref)
    db.commit()
    return {"document_type": payload.document_type, "template_id": payload.template_id}


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    order_id: uuid.UUID | None = None,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    query = db.query(Document).filter(Document.shop_id == current_user.shop_id)
    if order_id:
        query = query.filter(Document.order_id == order_id)
    return query.order_by(Document.created_at.desc()).all()


@router.post("/documents/issue", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def issue_document(
    payload: DocumentIssueRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> DocumentOut:
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == payload.order_id, Order.shop_id == current_user.shop_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    pref = (
        db.query(DocumentTemplatePreference)
        .filter(
            DocumentTemplatePreference.shop_id == current_user.shop_id,
            DocumentTemplatePreference.document_type == payload.type,
        )
        .first()
    )
    doc_number = f"{payload.type.value.upper()}-{datetime.now(timezone.utc):%Y%m}-{str(order.id)[:8]}"

    document = Document(
        shop_id=current_user.shop_id,
        order_id=order.id,
        type=payload.type,
        template_id=pref.template_id if pref else "classic",
        document_number=doc_number,
    )
    db.add(document)
    db.flush()  # populate document.id before rendering the file

    # FR-DOC-01/02: render a real PDF now, not just a document-number row.
    shop = current_user.shop
    pdf_path = render_document_pdf(document, order, shop_name=shop.name, currency=shop.currency)
    document.pdf_ref = pdf_path

    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/auto-issue", response_model=list[AutoIssueRuleOut])
def list_auto_issue_rules(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AutoIssueRuleOut]:
    """FR-DOC-04: list auto-issue toggles; seed defaults if the shop has none yet."""
    from app.models.document import DocumentType

    rules = (
        db.query(AutoIssueRule)
        .filter(AutoIssueRule.shop_id == current_user.shop_id)
        .order_by(AutoIssueRule.trigger)
        .all()
    )
    if not rules:
        for trigger, doc_type in DEFAULT_TRIGGERS:
            db.add(
                AutoIssueRule(
                    shop_id=current_user.shop_id,
                    trigger=trigger,
                    document_type=DocumentType(doc_type),
                    is_active=False,
                )
            )
        db.commit()
        rules = (
            db.query(AutoIssueRule)
            .filter(AutoIssueRule.shop_id == current_user.shop_id)
            .order_by(AutoIssueRule.trigger)
            .all()
        )
    return rules


@router.post("/documents/auto-issue", response_model=AutoIssueRuleOut, status_code=status.HTTP_201_CREATED)
def create_auto_issue_rule(
    payload: AutoIssueRuleCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> AutoIssueRuleOut:
    rule = AutoIssueRule(
        shop_id=current_user.shop_id,
        trigger=payload.trigger,
        document_type=payload.document_type,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/documents/auto-issue/{rule_id}", response_model=AutoIssueRuleOut)
def update_auto_issue_rule(
    rule_id: uuid.UUID,
    payload: AutoIssueRuleUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> AutoIssueRuleOut:
    rule = (
        db.query(AutoIssueRule)
        .filter(AutoIssueRule.id == rule_id, AutoIssueRule.shop_id == current_user.shop_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if payload.trigger is not None:
        rule.trigger = payload.trigger
    if payload.document_type is not None:
        rule.document_type = payload.document_type
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.shop_id == current_user.shop_id)
        .first()
    )
    if document is None or not document.pdf_ref:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document (or its PDF) not found")
    return FileResponse(
        document.pdf_ref,
        media_type="application/pdf",
        filename=f"{document.document_number}.pdf",
    )
