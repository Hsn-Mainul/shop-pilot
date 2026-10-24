import uuid

from pydantic import BaseModel

from app.models.integration import IntegrationCategory, IntegrationStatus


class IntegrationOut(BaseModel):
    id: uuid.UUID
    provider: str
    category: IntegrationCategory
    status: IntegrationStatus
    config: dict = {}

    model_config = {"from_attributes": True}


class IntegrationConnectRequest(BaseModel):
    config: dict = {}


class DialectPackOut(BaseModel):
    id: uuid.UUID
    language_code: str
    region_label: str
    accuracy_status: str
    word_error_rate: float | None

    model_config = {"from_attributes": True}


class DialectPackToggle(BaseModel):
    is_enabled: bool
