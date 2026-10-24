import uuid

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    customer_id: uuid.UUID
    order_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ReviewOut(ReviewCreate):
    id: uuid.UUID
    is_hidden: bool

    model_config = {"from_attributes": True}
