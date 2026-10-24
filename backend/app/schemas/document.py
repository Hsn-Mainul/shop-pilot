import uuid

from pydantic import BaseModel

from app.models.document import DocumentType


class DocumentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None
    type: DocumentType
    template_id: str | None
    document_number: str
    pdf_ref: str | None

    model_config = {"from_attributes": True}


class DocumentIssueRequest(BaseModel):
    order_id: uuid.UUID
    type: DocumentType


class TemplateDefaultUpdate(BaseModel):
    document_type: DocumentType
    template_id: str


class AutoIssueRuleCreate(BaseModel):
    trigger: str
    document_type: DocumentType
    is_active: bool = True


class AutoIssueRuleUpdate(BaseModel):
    trigger: str | None = None
    document_type: DocumentType | None = None
    is_active: bool | None = None


class AutoIssueRuleOut(BaseModel):
    id: uuid.UUID
    trigger: str
    document_type: DocumentType
    is_active: bool

    model_config = {"from_attributes": True}
