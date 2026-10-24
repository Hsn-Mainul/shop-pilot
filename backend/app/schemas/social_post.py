import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.social_post import SocialPostStatus


class SocialPostCreate(BaseModel):
    channel: str = "facebook"
    photo_urls: list[str] = Field(default_factory=list)
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    tagged_product_id: uuid.UUID | None = None
    send_price_to_inbox: bool = False
    first_comment: str | None = None
    page_id: str | None = None
    page_name: str | None = None
    error_message: str | None = None
    scheduled_at: datetime | None = None


class SocialPostOut(SocialPostCreate):
    id: uuid.UUID
    status: SocialPostStatus
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


class SocialPostUpdate(BaseModel):
    """Partial update — only editable while the post hasn't been published yet."""

    channel: str | None = None
    photo_urls: list[str] | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    tagged_product_id: uuid.UUID | None = None
    send_price_to_inbox: bool | None = None
    first_comment: str | None = None
    page_id: str | None = None
    page_name: str | None = None
    scheduled_at: datetime | None = None
