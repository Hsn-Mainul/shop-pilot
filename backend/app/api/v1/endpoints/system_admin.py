import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.app_pages_registry import APP_PAGE_LABELS, APP_PAGE_REGISTRY
from app.db.session import get_db
from app.models.app_page_access import AppPageUserPermission, AppPageVisibility
from app.models.integration import Integration
from app.models.page_ai_profile import PageAIProfile
from app.models.page_permission import PageUserPermission
from app.models.plan import AICreditLedgerEntry, Plan, PlanCode, ShopSubscription
from app.models.shop import Shop
from app.models.team_member import TeamMember, TeamRole
from app.schemas.system_admin import (
    AdminChangePlanRequest,
    AdminPageItemOut,
    AdminShopItemOut,
    AdjustTokensRequest,
    AppPagePermissionCreate,
    AppPagePermissionOut,
    AppPageVisibilityOut,
    AppPageVisibilityUpdate,
    CostAnalysisOut,
    PagePermissionCreate,
    PagePermissionOut,
    PageUsageBreakdownOut,
    PageUsagePointOut,
    PageVisibilityUpdate,
    PlanOut,
    PlanUpdate,
    SystemAdminOverviewOut,
    SystemUserOut,
    TokenAnalyticsOut,
    UserDashboardRowOut,
    UserUsageHistoryOut,
)

router = APIRouter(prefix="/system-admin", tags=["system-admin"])

# Rough average tokens (prompt + completion) per metered "credit" — consistent
# with the existing /token-analytics estimate.
CREDIT_TO_TOKENS = 350.0
WHOLESALE_RATE_PER_MILLION_USD = 0.70
BDT_TO_USD_RATE = 120.0


def _shop_credit_balance(db: Session, shop_id: uuid.UUID) -> float:
    granted = (
        db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
        .filter(AICreditLedgerEntry.shop_id == shop_id, AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount > 0)
        .scalar()
    )
    used = (
        db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
        .filter(AICreditLedgerEntry.shop_id == shop_id, AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
        .scalar()
    )
    return float(granted or 0) - abs(float(used or 0))


def _group_by_period(
    entries: list[AICreditLedgerEntry],
) -> tuple[list[PageUsagePointOut], list[PageUsagePointOut], list[PageUsagePointOut]]:
    """Bucket ledger entries by day / month / year using their timestamp."""
    daily: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    yearly: dict[str, float] = defaultdict(float)
    for e in entries:
        if e.created_at is None:
            continue
        amt = abs(float(e.amount))
        daily[e.created_at.strftime("%Y-%m-%d")] += amt
        monthly[e.created_at.strftime("%Y-%m")] += amt
        yearly[e.created_at.strftime("%Y")] += amt

    def _to_points(bucket: dict[str, float]) -> list[PageUsagePointOut]:
        return [
            PageUsagePointOut(period=period, credits_used=amt, tokens_used=amt * CREDIT_TO_TOKENS)
            for period, amt in sorted(bucket.items())
        ]

    return _to_points(daily), _to_points(monthly), _to_points(yearly)


@router.get("/overview", response_model=SystemAdminOverviewOut)
def get_system_admin_overview(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> SystemAdminOverviewOut:
    """Platform-level insights for the Product Owner."""
    total_shops = db.query(Shop).count()
    total_pages = db.query(PageAIProfile).count()
    visible_pages = db.query(PageAIProfile).filter(PageAIProfile.is_visible.is_(True)).count()
    invisible_pages = total_pages - visible_pages
    total_users = db.query(TeamMember).count()

    total_credits = (
        db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
        .filter(AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount > 0)
        .scalar()
    )

    return SystemAdminOverviewOut(
        total_shops=total_shops,
        total_pages=total_pages,
        visible_pages=visible_pages,
        invisible_pages=invisible_pages,
        total_users=total_users,
        total_credits_allocated=float(total_credits or 0),
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans_for_admin(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[PlanOut]:
    """List subscription tiers and usage rates."""
    return db.query(Plan).order_by(Plan.monthly_price.asc()).all()


@router.put("/plans/{plan_code}", response_model=PlanOut)
def update_plan_and_usage_rates(
    plan_code: PlanCode,
    payload: PlanUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> PlanOut:
    """Update subscription plan price, monthly grants, and extra usage rates."""
    plan = db.query(Plan).filter(Plan.code == plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if payload.name is not None:
        plan.name = payload.name
    if payload.monthly_price is not None:
        plan.monthly_price = payload.monthly_price
    if payload.monthly_ai_credits is not None:
        plan.monthly_ai_credits = payload.monthly_ai_credits
    if payload.monthly_voice_minutes is not None:
        plan.monthly_voice_minutes = payload.monthly_voice_minutes
    if payload.extra_credit_rate_per_k is not None:
        plan.extra_credit_rate_per_k = payload.extra_credit_rate_per_k
    if payload.extra_voice_rate_per_min is not None:
        plan.extra_voice_rate_per_min = payload.extra_voice_rate_per_min
    if payload.channel_limit is not None:
        plan.channel_limit = payload.channel_limit
    if payload.team_seat_limit is not None:
        plan.team_seat_limit = payload.team_seat_limit
    if payload.is_active is not None:
        plan.is_active = payload.is_active

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/pages", response_model=list[AdminPageItemOut])
def list_all_pages_for_admin(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[AdminPageItemOut]:
    """List all connected pages with visibility marks and assigned user permissions."""
    profiles = db.query(PageAIProfile).all()
    shops_map = {s.id: s.name for s in db.query(Shop).all()}

    # Fetch all permission rows
    permissions = db.query(PageUserPermission).all()
    users_map = {u.id: u for u in db.query(TeamMember).all()}

    perms_by_page: dict[str, list[PagePermissionOut]] = {}
    for p in permissions:
        u = users_map.get(p.user_id)
        if not u:
            continue
        item = PagePermissionOut(
            id=p.id,
            page_id=p.page_id,
            user_id=p.user_id,
            user_email=u.email,
            user_name=f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
            user_role=u.role.value if hasattr(u.role, "value") else str(u.role),
            can_view=p.can_view,
            can_manage=p.can_manage,
            created_at=p.created_at,
        )
        perms_by_page.setdefault(p.page_id, []).append(item)

    out = []
    for pr in profiles:
        out.append(
            AdminPageItemOut(
                page_id=pr.page_id,
                page_name=pr.page_name,
                platform=pr.platform,
                page_category=pr.page_category,
                detected_type=pr.detected_type,
                is_visible=getattr(pr, "is_visible", True),
                is_active=pr.is_active,
                auto_reply_enabled=pr.auto_reply_enabled,
                study_status=pr.study_status,
                shop_id=pr.shop_id,
                shop_name=shops_map.get(pr.shop_id, "Unknown Shop"),
                permitted_users=perms_by_page.get(pr.page_id, []),
            )
        )
    return out


@router.put("/pages/{page_id}/visibility", response_model=AdminPageItemOut)
def update_page_visibility(
    page_id: str,
    payload: PageVisibilityUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> AdminPageItemOut:
    """Set visible or invisible mark on a page.

    - If invisible: no regular user will see it.
    - If visible: only users with explicit permission will see it.
    """
    profile = db.query(PageAIProfile).filter(PageAIProfile.page_id == page_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    profile.is_visible = payload.is_visible
    db.add(profile)
    db.commit()
    db.refresh(profile)

    shop = db.get(Shop, profile.shop_id)
    perms = (
        db.query(PageUserPermission)
        .filter(PageUserPermission.page_id == page_id)
        .all()
    )
    users_map = {u.id: u for u in db.query(TeamMember).all()}
    permitted_list = []
    for p in perms:
        u = users_map.get(p.user_id)
        if u:
            permitted_list.append(
                PagePermissionOut(
                    id=p.id,
                    page_id=p.page_id,
                    user_id=p.user_id,
                    user_email=u.email,
                    user_name=f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                    user_role=u.role.value if hasattr(u.role, "value") else str(u.role),
                    can_view=p.can_view,
                    can_manage=p.can_manage,
                    created_at=p.created_at,
                )
            )

    return AdminPageItemOut(
        page_id=profile.page_id,
        page_name=profile.page_name,
        platform=profile.platform,
        page_category=profile.page_category,
        detected_type=profile.detected_type,
        is_visible=profile.is_visible,
        is_active=profile.is_active,
        auto_reply_enabled=profile.auto_reply_enabled,
        study_status=profile.study_status,
        shop_id=profile.shop_id,
        shop_name=shop.name if shop else "Shop",
        permitted_users=permitted_list,
    )


@router.post("/pages/{page_id}/permissions", response_model=PagePermissionOut)
def grant_user_page_permission(
    page_id: str,
    payload: PagePermissionCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> PagePermissionOut:
    """Grant page permission to a specific user."""
    profile = db.query(PageAIProfile).filter(PageAIProfile.page_id == page_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    target_user = db.get(TeamMember, payload.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    perm = (
        db.query(PageUserPermission)
        .filter(PageUserPermission.page_id == page_id, PageUserPermission.user_id == payload.user_id)
        .first()
    )
    if not perm:
        perm = PageUserPermission(
            shop_id=profile.shop_id,
            page_id=page_id,
            user_id=payload.user_id,
            can_view=payload.can_view,
            can_manage=payload.can_manage,
        )
        db.add(perm)
    else:
        perm.can_view = payload.can_view
        perm.can_manage = payload.can_manage

    db.commit()
    db.refresh(perm)

    return PagePermissionOut(
        id=perm.id,
        page_id=perm.page_id,
        user_id=perm.user_id,
        user_email=target_user.email,
        user_name=f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or target_user.email,
        user_role=target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role),
        can_view=perm.can_view,
        can_manage=perm.can_manage,
        created_at=perm.created_at,
    )


@router.delete("/pages/{page_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user_page_permission(
    page_id: str,
    user_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """Revoke user's permission for a page."""
    perm = (
        db.query(PageUserPermission)
        .filter(PageUserPermission.page_id == page_id, PageUserPermission.user_id == user_id)
        .first()
    )
    if perm:
        db.delete(perm)
        db.commit()


@router.get("/users", response_model=list[SystemUserOut])
def list_system_users_for_permissions(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[SystemUserOut]:
    """List team members available for page permission assignments."""
    users = db.query(TeamMember).filter(TeamMember.is_active.is_(True)).all()
    return [
        SystemUserOut(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            is_active=u.is_active,
        )
        for u in users
    ]


@router.get("/shops", response_model=list[AdminShopItemOut])
def list_all_shops_for_admin(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[AdminShopItemOut]:
    """List all registered tenant shops with their token usage, limits, and subscriptions."""
    shops = db.query(Shop).order_by(Shop.created_at.desc()).all()
    results: list[AdminShopItemOut] = []

    for s in shops:
        sub = db.query(ShopSubscription).filter(ShopSubscription.shop_id == s.id).first()
        granted = (
            db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
            .filter(AICreditLedgerEntry.shop_id == s.id, AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount > 0)
            .scalar()
        )
        used = (
            db.query(func.coalesce(func.sum(AICreditLedgerEntry.amount), 0))
            .filter(AICreditLedgerEntry.shop_id == s.id, AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
            .scalar()
        )
        total_granted = float(granted or 0)
        total_used = abs(float(used or 0))
        balance = total_granted - total_used

        channels_count = db.query(Integration).filter(Integration.shop_id == s.id).count()
        members_count = db.query(TeamMember).filter(TeamMember.shop_id == s.id).count()

        results.append(
            AdminShopItemOut(
                id=s.id,
                name=s.name,
                category=s.category,
                plan_tier=s.plan_tier or "free",
                subscription_status=sub.status if sub else "active",
                total_credits_granted=total_granted,
                total_credits_used=total_used,
                credits_balance=balance,
                channels_count=channels_count,
                members_count=members_count,
                created_at=s.created_at,
            )
        )
    return results


@router.post("/shops/{shop_id}/adjust-tokens", status_code=status.HTTP_200_OK)
def adjust_shop_tokens(
    shop_id: uuid.UUID,
    payload: AdjustTokensRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Manually grant, top-up, or deduct tokens/credits for any tenant shop."""
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    entry = AICreditLedgerEntry(
        shop_id=shop.id,
        kind=payload.kind,
        amount=payload.amount,
        reason=f"admin_override:{payload.reason}",
    )
    db.add(entry)
    db.commit()
    return {"status": "ok", "message": f"Adjusted {payload.amount} {payload.kind} for shop '{shop.name}'"}


@router.post("/shops/{shop_id}/change-plan", status_code=status.HTTP_200_OK)
def change_shop_plan_as_admin(
    shop_id: uuid.UUID,
    payload: AdminChangePlanRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """System Admin direct plan upgrade or downgrade for a shop."""
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    shop.plan_tier = payload.plan_code
    db.add(shop)

    sub = db.query(ShopSubscription).filter(ShopSubscription.shop_id == shop.id).first()
    if sub:
        sub.plan_code = PlanCode(payload.plan_code)
    else:
        sub = ShopSubscription(
            shop_id=shop.id,
            plan_code=PlanCode(payload.plan_code),
            status="active",
        )
        db.add(sub)

    db.commit()
    return {"status": "ok", "message": f"Updated plan for '{shop.name}' to {payload.plan_code}"}


@router.get("/token-analytics", response_model=TokenAnalyticsOut)
def get_token_analytics(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> TokenAnalyticsOut:
    """Calculate platform-wide token consumption, channel breakdown, and wholesale provider margin."""
    used_entries = (
        db.query(AICreditLedgerEntry)
        .filter(AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
        .all()
    )

    total_credits_used = sum(abs(float(e.amount)) for e in used_entries)
    # 1 credit = ~350 prompt/completion tokens average in conversation
    total_tokens_consumed = total_credits_used * 350.0

    # Channel breakdown by parsing reason (e.g. ai_reply:facebook, comment_reply:instagram)
    channel_counts: dict[str, float] = {
        "facebook": 0.0,
        "instagram": 0.0,
        "whatsapp": 0.0,
        "telegram": 0.0,
        "website": 0.0,
        "other": 0.0,
    }

    for e in used_entries:
        amt = abs(float(e.amount))
        r = (e.reason or "").lower()
        if "facebook" in r or "messenger" in r or "feed" in r:
            channel_counts["facebook"] += amt
        elif "instagram" in r:
            channel_counts["instagram"] += amt
        elif "whatsapp" in r:
            channel_counts["whatsapp"] += amt
        elif "telegram" in r:
            channel_counts["telegram"] += amt
        elif "web" in r or "livechat" in r:
            channel_counts["website"] += amt
        else:
            channel_counts["other"] += amt

    # Wholesale API Cost calculation (Groq average ~$0.70 per 1M tokens)
    wholesale_rate_per_million = 0.70
    estimated_wholesale_cost = (total_tokens_consumed / 1_000_000.0) * wholesale_rate_per_million

    # Revenue calculation: sum of monthly subscriptions
    plans_map = {p.code: float(p.monthly_price) for p in db.query(Plan).all()}
    all_shops = db.query(Shop).all()
    total_revenue_bdt = sum(plans_map.get(s.plan_tier, 0.0) for s in all_shops)
    total_revenue_usd = total_revenue_bdt / 120.0  # Approx BDT to USD conversion

    margin = 0.0
    if total_revenue_usd > 0:
        margin = max(0.0, ((total_revenue_usd - estimated_wholesale_cost) / total_revenue_usd) * 100.0)
    elif estimated_wholesale_cost == 0:
        margin = 100.0

    # Top consuming shops
    top_shops_rows = (
        db.query(Shop.id, Shop.name, Shop.plan_tier, func.sum(AICreditLedgerEntry.amount).label("used"))
        .join(AICreditLedgerEntry, Shop.id == AICreditLedgerEntry.shop_id)
        .filter(AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
        .group_by(Shop.id, Shop.name, Shop.plan_tier)
        .order_by(func.sum(AICreditLedgerEntry.amount).asc())
        .limit(5)
        .all()
    )

    top_shops = [
        {
            "shop_id": str(r[0]),
            "shop_name": r[1],
            "plan_tier": r[2],
            "credits_used": abs(float(r[3] or 0)),
        }
        for r in top_shops_rows
    ]

    return TokenAnalyticsOut(
        total_tokens_consumed=total_tokens_consumed,
        total_credits_consumed=total_credits_used,
        channel_breakdown=channel_counts,
        estimated_wholesale_cost_usd=round(estimated_wholesale_cost, 4),
        total_subscriber_revenue_usd=round(total_revenue_usd, 2),
        net_margin_percentage=round(margin, 1),
        top_consuming_shops=top_shops,
    )


@router.get("/dashboard", response_model=list[UserDashboardRowOut])
def get_admin_dashboard(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[UserDashboardRowOut]:
    """Dashboard: every user (shop/tenant), their connected social pages, and
    their AI usage today / this month / all-time — the entry point for
    drilling into a specific user's history."""
    shops = db.query(Shop).order_by(Shop.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    today_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")

    all_entries = (
        db.query(AICreditLedgerEntry)
        .filter(AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
        .all()
    )
    entries_by_shop: dict[uuid.UUID, list[AICreditLedgerEntry]] = defaultdict(list)
    for e in all_entries:
        entries_by_shop[e.shop_id].append(e)

    all_pages = db.query(PageAIProfile).all()
    pages_by_shop: dict[uuid.UUID, list[PageAIProfile]] = defaultdict(list)
    for p in all_pages:
        pages_by_shop[p.shop_id].append(p)

    rows: list[UserDashboardRowOut] = []
    for s in shops:
        shop_entries = entries_by_shop.get(s.id, [])
        total_used = sum(abs(float(e.amount)) for e in shop_entries)
        used_today = sum(
            abs(float(e.amount)) for e in shop_entries if e.created_at and e.created_at.strftime("%Y-%m-%d") == today_key
        )
        used_month = sum(
            abs(float(e.amount)) for e in shop_entries if e.created_at and e.created_at.strftime("%Y-%m") == month_key
        )
        last_active = max((e.created_at for e in shop_entries if e.created_at), default=None)
        shop_pages = pages_by_shop.get(s.id, [])
        rows.append(
            UserDashboardRowOut(
                shop_id=s.id,
                shop_name=s.name,
                plan_tier=s.plan_tier or "free",
                pages_count=len(shop_pages),
                platforms=sorted({p.platform for p in shop_pages}),
                credits_used_today=used_today,
                credits_used_this_month=used_month,
                credits_used_total=total_used,
                last_active_at=last_active,
            )
        )
    return rows


@router.get("/users/{shop_id}/usage", response_model=UserUsageHistoryOut)
def get_user_usage_history(
    shop_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> UserUsageHistoryOut:
    """Per-user (shop) usage history broken down by each of their connected
    social pages, and by day / month / year — the Dashboard drill-down."""
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found")

    entries = (
        db.query(AICreditLedgerEntry)
        .filter(
            AICreditLedgerEntry.shop_id == shop_id,
            AICreditLedgerEntry.kind == "text_credit",
            AICreditLedgerEntry.amount < 0,
        )
        .all()
    )
    pages_by_id = {p.page_id: p for p in db.query(PageAIProfile).filter(PageAIProfile.shop_id == shop_id).all()}

    entries_by_page: dict[str, list[AICreditLedgerEntry]] = defaultdict(list)
    for e in entries:
        entries_by_page[e.page_id or "unattributed"].append(e)

    page_breakdowns: list[PageUsageBreakdownOut] = []
    for page_id, page_entries in entries_by_page.items():
        page = pages_by_id.get(page_id)
        total = sum(abs(float(e.amount)) for e in page_entries)
        daily, monthly, yearly = _group_by_period(page_entries)
        page_breakdowns.append(
            PageUsageBreakdownOut(
                page_id=page_id,
                page_name=page.page_name if page else "General / Manual AI Usage",
                platform=page.platform if page else "other",
                credits_used_total=total,
                tokens_used_total=total * CREDIT_TO_TOKENS,
                daily=daily,
                monthly=monthly,
                yearly=yearly,
            )
        )
    page_breakdowns.sort(key=lambda p: p.credits_used_total, reverse=True)

    shop_daily, shop_monthly, shop_yearly = _group_by_period(entries)

    return UserUsageHistoryOut(
        shop_id=shop.id,
        shop_name=shop.name,
        plan_tier=shop.plan_tier or "free",
        credits_balance=_shop_credit_balance(db, shop_id),
        pages=page_breakdowns,
        daily=shop_daily,
        monthly=shop_monthly,
        yearly=shop_yearly,
    )


@router.get("/cost-analysis", response_model=CostAnalysisOut)
def get_cost_analysis(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> CostAnalysisOut:
    """Platform-wide cost analysis: wholesale LLM spend vs subscriber revenue,
    broken down by day / month / year, plus the pages driving the most cost."""
    entries = (
        db.query(AICreditLedgerEntry)
        .filter(AICreditLedgerEntry.kind == "text_credit", AICreditLedgerEntry.amount < 0)
        .all()
    )
    total_credits = sum(abs(float(e.amount)) for e in entries)
    total_tokens = total_credits * CREDIT_TO_TOKENS
    total_wholesale_cost = (total_tokens / 1_000_000.0) * WHOLESALE_RATE_PER_MILLION_USD

    plans_map = {p.code: float(p.monthly_price) for p in db.query(Plan).all()}
    all_shops = db.query(Shop).all()
    total_revenue_bdt = sum(plans_map.get(s.plan_tier, 0.0) for s in all_shops)
    total_revenue_usd = total_revenue_bdt / BDT_TO_USD_RATE

    margin = 0.0
    if total_revenue_usd > 0:
        margin = max(0.0, ((total_revenue_usd - total_wholesale_cost) / total_revenue_usd) * 100.0)
    elif total_wholesale_cost == 0:
        margin = 100.0

    def _to_cost_series(points: list[PageUsagePointOut]) -> list[dict]:
        return [
            {
                "period": p.period,
                "credits_used": p.credits_used,
                "tokens_used": p.tokens_used,
                "cost_usd": round((p.tokens_used / 1_000_000.0) * WHOLESALE_RATE_PER_MILLION_USD, 4),
            }
            for p in points
        ]

    daily, monthly, yearly = _group_by_period(entries)

    page_names = {p.page_id: (p.page_name, p.platform) for p in db.query(PageAIProfile).all()}
    credits_by_page: dict[str, float] = defaultdict(float)
    for e in entries:
        credits_by_page[e.page_id or "unattributed"] += abs(float(e.amount))

    top_pages = []
    for page_id, credits in sorted(credits_by_page.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        tokens = credits * CREDIT_TO_TOKENS
        name, platform = page_names.get(page_id, ("General / Manual AI Usage", "other"))
        top_pages.append(
            {
                "page_id": page_id,
                "page_name": name,
                "platform": platform,
                "credits_used": credits,
                "tokens_used": tokens,
                "cost_usd": round((tokens / 1_000_000.0) * WHOLESALE_RATE_PER_MILLION_USD, 4),
            }
        )

    return CostAnalysisOut(
        wholesale_rate_per_million_usd=WHOLESALE_RATE_PER_MILLION_USD,
        bdt_to_usd_rate=BDT_TO_USD_RATE,
        total_tokens_consumed=total_tokens,
        total_wholesale_cost_usd=round(total_wholesale_cost, 4),
        total_subscriber_revenue_usd=round(total_revenue_usd, 2),
        net_margin_percentage=round(margin, 1),
        daily=_to_cost_series(daily),
        monthly=_to_cost_series(monthly),
        yearly=_to_cost_series(yearly),
        top_pages_by_cost=top_pages,
    )


# ============================================================================
# Internal App Page Visibility — controls access to OUR OWN application
# modules (Setup, Integrations, Products, ...), separate from social media
# Page visibility (PageAIProfile.is_visible / PageUserPermission above).
# ============================================================================


def _app_page_permission_out(perm: AppPageUserPermission, user: TeamMember) -> AppPagePermissionOut:
    return AppPagePermissionOut(
        id=perm.id,
        page_key=perm.page_key,
        user_id=perm.user_id,
        user_email=user.email,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
        user_role=user.role.value if hasattr(user.role, "value") else str(user.role),
    )


@router.get("/app-pages", response_model=list[AppPageVisibilityOut])
def list_app_pages_for_admin(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[AppPageVisibilityOut]:
    """List every internal application page/module with its visibility mark
    (visible to all vs restricted) and, if restricted, the permitted users."""
    configs = {c.page_key: c for c in db.query(AppPageVisibility).all()}
    perms = db.query(AppPageUserPermission).all()
    users_map = {u.id: u for u in db.query(TeamMember).all()}

    perms_by_page: dict[str, list[AppPagePermissionOut]] = {}
    for p in perms:
        u = users_map.get(p.user_id)
        if not u:
            continue
        perms_by_page.setdefault(p.page_key, []).append(_app_page_permission_out(p, u))

    out: list[AppPageVisibilityOut] = []
    for page_key, label in APP_PAGE_REGISTRY:
        cfg = configs.get(page_key)
        out.append(
            AppPageVisibilityOut(
                page_key=page_key,
                label=label,
                is_restricted=bool(cfg.is_restricted) if cfg else False,
                permitted_users=perms_by_page.get(page_key, []),
            )
        )
    return out


@router.put("/app-pages/{page_key}/visibility", response_model=AppPageVisibilityOut)
def update_app_page_visibility(
    page_key: str,
    payload: AppPageVisibilityUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> AppPageVisibilityOut:
    """Mark an internal app page visible-to-all or restricted-to-permitted-users."""
    if page_key not in APP_PAGE_LABELS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown app page")

    cfg = db.query(AppPageVisibility).filter(AppPageVisibility.page_key == page_key).first()
    if cfg is None:
        cfg = AppPageVisibility(page_key=page_key, is_restricted=payload.is_restricted)
    else:
        cfg.is_restricted = payload.is_restricted
    db.add(cfg)
    db.commit()

    perms = db.query(AppPageUserPermission).filter(AppPageUserPermission.page_key == page_key).all()
    users_map = {u.id: u for u in db.query(TeamMember).all()}
    permitted = [
        _app_page_permission_out(p, users_map[p.user_id]) for p in perms if p.user_id in users_map
    ]

    return AppPageVisibilityOut(
        page_key=page_key,
        label=APP_PAGE_LABELS[page_key],
        is_restricted=cfg.is_restricted,
        permitted_users=permitted,
    )


@router.post("/app-pages/{page_key}/permissions", response_model=AppPagePermissionOut)
def grant_app_page_permission(
    page_key: str,
    payload: AppPagePermissionCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> AppPagePermissionOut:
    """Grant a specific user access to a restricted internal app page."""
    if page_key not in APP_PAGE_LABELS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown app page")

    target_user = db.get(TeamMember, payload.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    perm = (
        db.query(AppPageUserPermission)
        .filter(AppPageUserPermission.page_key == page_key, AppPageUserPermission.user_id == payload.user_id)
        .first()
    )
    if not perm:
        perm = AppPageUserPermission(page_key=page_key, user_id=payload.user_id)
        db.add(perm)
        db.commit()
        db.refresh(perm)

    return _app_page_permission_out(perm, target_user)


@router.delete("/app-pages/{page_key}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_app_page_permission(
    page_key: str,
    user_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """Revoke a user's access to a restricted internal app page."""
    perm = (
        db.query(AppPageUserPermission)
        .filter(AppPageUserPermission.page_key == page_key, AppPageUserPermission.user_id == user_id)
        .first()
    )
    if perm:
        db.delete(perm)
        db.commit()

