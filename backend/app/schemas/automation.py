import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.automation import AutomationKind


class AutomationRuleCreate(BaseModel):
    kind: AutomationKind = AutomationKind.RULE
    name: str
    trigger: str
    action: str
    config: dict = {}


class AutomationRuleOut(AutomationRuleCreate):
    id: uuid.UUID
    is_active: bool
    run_count: int
    failure_count: int

    model_config = {"from_attributes": True}


class BulkCampaignCreate(BaseModel):
    channel: str  # email, sms, whatsapp, voice
    segment: str
    message_template: str
    scheduled_at: datetime | None = None


class BulkCampaignOut(BulkCampaignCreate):
    id: uuid.UUID
    status: str
    sent_count: int
    delivered_count: int
    opted_out_excluded_count: int

    model_config = {"from_attributes": True}


class RecipeOut(BaseModel):
    code: str
    name: str
    description: str
    trigger: str
    action: str
    config: dict = {}
    installed: bool = False


class RecipeInstallRequest(BaseModel):
    code: str
