import uuid

from pydantic import BaseModel, Field

from app.models.ai_knowledge import KnowledgeCategory


class KnowledgeItemCreate(BaseModel):
    category: KnowledgeCategory
    title: str
    content: str
    source_file_ref: str | None = None


class KnowledgeItemOut(KnowledgeItemCreate):
    id: uuid.UUID
    is_pending_approval: bool
    has_embedding: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        if hasattr(obj, "embedding") and obj.embedding:
            instance.has_embedding = True
        return instance


class AskRequest(BaseModel):
    question: str
    page_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    used_knowledge_item_ids: list[uuid.UUID] = []
    used_product_ids: list[uuid.UUID] = []


class SocialCaptionRequest(BaseModel):
    kind: str = "caption"  # caption | hashtags
    language: str = "en"  # en | bn
    page_id: str | None = None
    product_id: uuid.UUID | None = None
    photo_url: str | None = None
    context: str | None = None


class SocialCaptionResponse(BaseModel):
    answer: str
    used_image: bool = False


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=20)
    page_id: str | None = None


class RagSearchKnowledgeItem(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    category: str
    similarity: float


class RagSearchProductItem(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None = None
    price: float
    description: str | None = None
    similarity: float
    text_summary: str


class RagSearchResponse(BaseModel):
    query: str
    mode: str  # "vector" | "lexical_fallback"
    knowledge: list[RagSearchKnowledgeItem] = []
    products: list[RagSearchProductItem] = []


class RagStatusResponse(BaseModel):
    ollama_online: bool
    ollama_version: str | None = None
    chat_model: str
    chat_ready: bool
    embed_model: str
    embed_ready: bool
    knowledge_indexed: int
    knowledge_total: int
    products_indexed: int
    products_total: int
    models_available: list[str] = []


class RagReindexResponse(BaseModel):
    shop_id: str
    indexed_knowledge_count: int
    total_knowledge_count: int
    indexed_products_count: int
    total_products_count: int
    message: str
