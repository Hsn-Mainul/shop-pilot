import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class KnowledgeCategory(str, enum.Enum):
    SHOP_FACT = "shop_fact"
    FAQ_POLICY = "faq_policy"
    INSTRUCTION = "instruction"
    FILE = "file"


class AIKnowledgeItem(UUIDMixin, TimestampMixin, Base):
    """Facts/FAQs/instructions the merchant has taught or approved (FR-AI-03/04)."""

    __tablename__ = "ai_knowledge_items"

    shop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shops.id"), index=True)
    category: Mapped[KnowledgeCategory] = mapped_column(Enum(KnowledgeCategory))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source_file_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_pending_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    inferred_from_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    # Dense vector representation from Ollama/RAG embed model
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    # Page-specific knowledge scoping (e.g. BallotBuzz FB page vs general shop)
    page_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
