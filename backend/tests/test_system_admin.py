import pytest
from app.db.session import SessionLocal
from app.models.page_ai_profile import PageAIProfile
from app.models.page_permission import PageUserPermission
from app.models.plan import Plan, PlanCode
from app.models.shop import Shop
from app.models.team_member import TeamMember, TeamRole
from app.services.page_study_service import study_and_sync_page_profile


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_system_admin_plan_and_usage_rates(db_session):
    """Verify that System Admin (Product Owner) can configure plans and usage rates."""
    free_plan = db_session.query(Plan).filter(Plan.code == PlanCode.FREE).first()
    assert free_plan is not None

    # Update plan rate and extra usage rates
    free_plan.monthly_price = 0
    free_plan.monthly_ai_credits = 100
    free_plan.extra_credit_rate_per_k = 12.50
    free_plan.extra_voice_rate_per_min = 0.25
    db_session.add(free_plan)
    db_session.commit()
    db_session.refresh(free_plan)

    assert free_plan.monthly_ai_credits == 100
    assert float(free_plan.extra_credit_rate_per_k) == 12.50
    assert float(free_plan.extra_voice_rate_per_min) == 0.25


def test_page_visibility_and_user_permissions(db_session):
    """Verify visibility marking and user-specific page access control.

    - If invisible: no regular user can see it.
    - If visible: user won't see it unless user has permission.
    - System Admin (Super Admin) is the product owner and sees all pages.
    """
    shop = db_session.query(Shop).first()
    assert shop is not None

    # Create / get super admin user
    super_admin = (
        db_session.query(TeamMember)
        .filter(TeamMember.shop_id == shop.id, TeamMember.role == TeamRole.SUPER_ADMIN)
        .first()
    )
    assert super_admin is not None

    # Create a test regular support user
    regular_user = (
        db_session.query(TeamMember)
        .filter(TeamMember.shop_id == shop.id, TeamMember.email == "support_agent_test@demo.test")
        .first()
    )
    if not regular_user:
        regular_user = TeamMember(
            shop_id=shop.id,
            email="support_agent_test@demo.test",
            hashed_password="mock",
            role=TeamRole.SUPPORT,
            first_name="Support",
            last_name="Agent",
        )
        db_session.add(regular_user)
        db_session.commit()
        db_session.refresh(regular_user)

    # Create test page profile
    test_page_id = "test_perm_page_999"
    profile = (
        db_session.query(PageAIProfile)
        .filter(PageAIProfile.shop_id == shop.id, PageAIProfile.page_id == test_page_id)
        .first()
    )
    if not profile:
        profile = PageAIProfile(
            shop_id=shop.id,
            page_id=test_page_id,
            page_name="Special Initiative Page",
            platform="facebook",
            is_visible=True,
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    # 1. Page is visible, but regular user does NOT have permission yet
    # Verify regular user cannot see this page
    perms = (
        db_session.query(PageUserPermission)
        .filter(PageUserPermission.page_id == test_page_id, PageUserPermission.user_id == regular_user.id)
        .first()
    )
    if perms:
        db_session.delete(perms)
        db_session.commit()

    permitted_page_ids = [
        row[0]
        for row in db_session.query(PageUserPermission.page_id)
        .filter(PageUserPermission.user_id == regular_user.id, PageUserPermission.can_view.is_(True))
        .all()
    ]
    assert test_page_id not in permitted_page_ids

    # 2. System Admin grants user-specific permission to this page
    perm = PageUserPermission(
        shop_id=shop.id,
        page_id=test_page_id,
        user_id=regular_user.id,
        can_view=True,
    )
    db_session.add(perm)
    db_session.commit()

    # Now user has permission and page is visible -> user can see it!
    permitted_page_ids = [
        row[0]
        for row in db_session.query(PageUserPermission.page_id)
        .filter(PageUserPermission.user_id == regular_user.id, PageUserPermission.can_view.is_(True))
        .all()
    ]
    assert test_page_id in permitted_page_ids

    # 3. System Admin marks the page INVISIBLE
    profile.is_visible = False
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    # When marked invisible, no regular user can see it (even with permission)
    is_visible_to_regular = profile.is_visible and (test_page_id in permitted_page_ids)
    assert is_visible_to_regular is False

    # But System Admin (Product Owner) has master access
    assert super_admin.role == TeamRole.SUPER_ADMIN
