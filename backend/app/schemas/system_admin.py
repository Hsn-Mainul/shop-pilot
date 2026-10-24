import datetime
import uuid
from pydantic import BaseModel, ConfigDict


class PlanUpdate(BaseModel):
    name: str | None = None
    monthly_price: float | None = None
    monthly_ai_credits: int | None = None
    monthly_voice_minutes: int | None = None
    extra_credit_rate_per_k: float | None = None
    extra_voice_rate_per_min: float | None = None
    channel_limit: int | None = None
    team_seat_limit: int | None = None
    is_active: bool | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    monthly_price: float
    monthly_ai_credits: int
    monthly_voice_minutes: int
    extra_credit_rate_per_k: float = 10.0
    extra_voice_rate_per_min: float = 0.20
    channel_limit: int
    team_seat_limit: int
    is_active: bool = True


class PageVisibilityUpdate(BaseModel):
    is_visible: bool


class PagePermissionCreate(BaseModel):
    user_id: uuid.UUID
    can_view: bool = True
    can_manage: bool = False


class PagePermissionOut(BaseModel):
    id: uuid.UUID
    page_id: str
    user_id: uuid.UUID
    user_email: str
    user_name: str
    user_role: str
    can_view: bool
    can_manage: bool
    created_at: datetime.datetime


class AdminPageItemOut(BaseModel):
    page_id: str
    page_name: str
    platform: str
    page_category: str | None = None
    detected_type: str = "general"
    is_visible: bool = True
    is_active: bool = True
    auto_reply_enabled: bool = True
    study_status: str = "not_studied"
    shop_id: uuid.UUID
    shop_name: str
    permitted_users: list[PagePermissionOut] = []


class SystemUserOut(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    role: str
    is_active: bool


class SystemAdminOverviewOut(BaseModel):
    total_shops: int
    total_pages: int
    visible_pages: int
    invisible_pages: int
    total_users: int
    total_credits_allocated: float


class AdminShopItemOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None = None
    plan_tier: str
    subscription_status: str
    total_credits_granted: float
    total_credits_used: float
    credits_balance: float
    channels_count: int
    members_count: int
    created_at: datetime.datetime | None = None


class AdjustTokensRequest(BaseModel):
    amount: float
    kind: str = "text_credit"
    reason: str = "admin_adjustment"


class AdminChangePlanRequest(BaseModel):
    plan_code: str


class TokenAnalyticsOut(BaseModel):
    total_tokens_consumed: float
    total_credits_consumed: float
    channel_breakdown: dict[str, float]
    estimated_wholesale_cost_usd: float
    total_subscriber_revenue_usd: float
    net_margin_percentage: float
    top_consuming_shops: list[dict]


class AppPagePermissionOut(BaseModel):
    id: uuid.UUID
    page_key: str
    user_id: uuid.UUID
    user_email: str
    user_name: str
    user_role: str


class AppPageVisibilityOut(BaseModel):
    page_key: str
    label: str
    is_restricted: bool
    permitted_users: list[AppPagePermissionOut] = []


class AppPageVisibilityUpdate(BaseModel):
    is_restricted: bool


class AppPagePermissionCreate(BaseModel):
    user_id: uuid.UUID


class UserDashboardRowOut(BaseModel):
    """One row of the System Admin "Users" list / Dashboard table — a tenant
    (shop) with its connected social pages and overall AI usage."""

    shop_id: uuid.UUID
    shop_name: str
    plan_tier: str
    pages_count: int
    platforms: list[str] = []
    credits_used_today: float
    credits_used_this_month: float
    credits_used_total: float
    last_active_at: datetime.datetime | None = None


class PageUsagePointOut(BaseModel):
    period: str  # e.g. "2026-10-24", "2026-10", or "2026"
    credits_used: float
    tokens_used: float


class PageUsageBreakdownOut(BaseModel):
    page_id: str
    page_name: str
    platform: str
    credits_used_total: float
    tokens_used_total: float
    daily: list[PageUsagePointOut] = []
    monthly: list[PageUsagePointOut] = []
    yearly: list[PageUsagePointOut] = []


class UserUsageHistoryOut(BaseModel):
    """Per-user (shop) usage history, broken down by each connected social
    page, and by day / month / year."""

    shop_id: uuid.UUID
    shop_name: str
    plan_tier: str
    credits_balance: float
    pages: list[PageUsageBreakdownOut] = []
    daily: list[PageUsagePointOut] = []
    monthly: list[PageUsagePointOut] = []
    yearly: list[PageUsagePointOut] = []


class CostAnalysisOut(BaseModel):
    """Platform-wide cost analysis: wholesale LLM spend vs subscriber revenue
    over time, broken down by day / month / year."""

    wholesale_rate_per_million_usd: float
    bdt_to_usd_rate: float
    total_tokens_consumed: float
    total_wholesale_cost_usd: float
    total_subscriber_revenue_usd: float
    net_margin_percentage: float
    daily: list[dict] = []
    monthly: list[dict] = []
    yearly: list[dict] = []
    top_pages_by_cost: list[dict] = []
