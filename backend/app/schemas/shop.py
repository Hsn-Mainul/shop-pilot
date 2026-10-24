import uuid

from pydantic import BaseModel


class ShopBase(BaseModel):
    name: str
    category: str | None = None
    currency: str = "BDT"
    timezone: str = "Asia/Dhaka"
    address: str | None = None
    opening_hours: dict = {}
    delivery_charge_inside_city: float | None = None
    delivery_charge_outside_city: float | None = None
    auto_hide_spam_comments: bool = True
    auto_hide_phone_numbers_in_comments: bool = True
    ai_auto_reply_comments: bool = False
    ai_module_toggles: dict = {}


class ShopCreate(ShopBase):
    pass


class ShopUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    currency: str | None = None
    timezone: str | None = None
    address: str | None = None
    opening_hours: dict | None = None
    delivery_charge_inside_city: float | None = None
    delivery_charge_outside_city: float | None = None
    auto_hide_spam_comments: bool | None = None
    auto_hide_phone_numbers_in_comments: bool | None = None
    ai_auto_reply_comments: bool | None = None
    ai_module_toggles: dict | None = None


class ShopOut(ShopBase):
    id: uuid.UUID
    plan_tier: str

    model_config = {"from_attributes": True}


class SetupChecklistStep(BaseModel):
    key: str
    label: str
    group: str
    is_done: bool
    estimated_minutes: int


class SetupChecklistOut(BaseModel):
    percent_complete: int
    steps_done: int
    steps_total: int
    up_next: SetupChecklistStep | None
    steps: list[SetupChecklistStep]


class TeamMemberOut(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class TeamMemberInvite(BaseModel):
    email: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
