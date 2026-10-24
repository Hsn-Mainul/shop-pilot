import datetime
import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict


class PageAIProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_id: uuid.UUID
    page_id: str
    platform: str
    page_name: str
    page_category: str | None = None
    detected_type: str = "general"

    about: str | None = None
    bio: str | None = None
    mission: str | None = None
    website: str | None = None
    raw_study_data: dict[str, Any] = {}

    ai_persona_name: str
    ai_role_description: str | None = None
    system_instructions: str | None = None
    tone: str
    key_topics: list[str] = []
    dos_and_donts: str | None = None

    is_active: bool = True
    is_visible: bool = True
    auto_reply_enabled: bool = True
    include_product_catalog: bool = False

    study_status: str = "not_studied"
    last_studied_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PageAIProfileUpdate(BaseModel):
    ai_persona_name: str | None = None
    ai_role_description: str | None = None
    system_instructions: str | None = None
    tone: str | None = None
    key_topics: list[str] | None = None
    dos_and_donts: str | None = None
    is_active: bool | None = None
    auto_reply_enabled: bool | None = None
    include_product_catalog: bool | None = None


class PageStudyTriggerRequest(BaseModel):
    custom_context: str | None = None


class PageKnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str = "shop_fact"


class PageSimulateChatRequest(BaseModel):
    message: str


class PageSimulateChatResponse(BaseModel):
    reply: str
    persona: str
    detected_type: str
    used_knowledge_count: int
    used_products_count: int
