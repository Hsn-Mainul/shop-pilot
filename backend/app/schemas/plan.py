from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.plan import PlanCode


class PlanOut(BaseModel):
    code: PlanCode
    name: str
    monthly_price: Decimal
    channel_limit: int
    team_seat_limit: int
    monthly_ai_credits: int
    monthly_voice_minutes: int

    model_config = {"from_attributes": True}


class ShopPlanOut(BaseModel):
    plan_code: PlanCode
    status: str
    renews_at: datetime | None
    ai_credits_used_this_month: Decimal
    ai_credits_remaining: Decimal

    model_config = {"from_attributes": True}


class PlanChangeRequest(BaseModel):
    plan_code: PlanCode
