import uuid

from pydantic import BaseModel

from app.models.loyalty import RewardStatus


class LoyaltyRewardOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    milestone_order_number: int
    draft_message: str
    status: RewardStatus

    model_config = {"from_attributes": True}


class LoyaltyRewardDecision(BaseModel):
    approve: bool
