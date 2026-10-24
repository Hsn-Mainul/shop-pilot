import pytest
from app.api.v1.endpoints.ai import _answer_from_shop_knowledge
from app.db.session import SessionLocal
from app.models.ai_knowledge import AIKnowledgeItem, KnowledgeCategory
from app.models.integration import Integration, IntegrationStatus
from app.models.shop import Shop
from app.models.page_ai_profile import PageAIType
from app.services.page_study_service import study_and_sync_page_profile


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_study_and_train_connected_page_dynamically(db_session):
    """Verify that the AI dynamically reads the page name and content from the connected page,

    studies its nature from the page's actual data, and configures matching persona and guardrails.
    """
    shop = db_session.query(Shop).first()
    assert shop is not None, "Shop must exist"

    # 1. Discover connected page dynamically from integration records
    fb_integration = (
        db_session.query(Integration)
        .filter(Integration.shop_id == shop.id, Integration.provider == "facebook", Integration.status == IntegrationStatus.CONNECTED)
        .first()
    )

    # Use first available connected page from the database or dynamic page payload
    pages_list = (fb_integration.config or {}).get("pages", []) if fb_integration else []
    if pages_list:
        connected_page = pages_list[0]
        page_id = str(connected_page.get("id"))
        page_name = connected_page.get("name")
        page_category = connected_page.get("category", "General")
        page_token = connected_page.get("access_token")
    else:
        page_id = "dyn_page_test_123"
        page_name = "CivicVoice Bangladesh"
        page_category = "Political Organization"
        page_token = None

    # 2. AI studies the page by reading its actual name, category, and data
    profile = study_and_sync_page_profile(
        db=db_session,
        shop_id=shop.id,
        page_id=page_id,
        page_name=page_name,
        category=page_category,
        page_access_token=page_token,
        platform="facebook",
    )

    # Verify AI read the exact name from the connected page
    assert profile.page_name == page_name
    assert profile.page_id == page_id

    # Verify AI studied the nature of the page
    assert profile.detected_type in [e.value for e in PageAIType]
    assert profile.ai_persona_name is not None
    assert profile.system_instructions is not None

    # If the page nature is non-retail/political, ensure catalog ordering is disabled
    if profile.detected_type in ["political_campaign", "non_profit", "community"]:
        assert profile.include_product_catalog is False
        assert any(term in profile.dos_and_donts.lower() for term in ["product", "furniture", "sales", "commercial", "order"])

    # 3. Train a page-specific policy
    test_question = "What is the mission of this organization?"
    test_answer = f"The primary mission of {page_name} is public awareness and community empowerment."

    k_item = AIKnowledgeItem(
        shop_id=shop.id,
        page_id=profile.page_id,
        category=KnowledgeCategory.SHOP_FACT,
        title=f"Mission of {page_name}",
        content=test_answer,
        is_pending_approval=False,
    )
    db_session.add(k_item)
    db_session.commit()

    # 4. Ask the AI assistant scoped to this page
    reply = _answer_from_shop_knowledge(
        db_session, shop, test_question, page_id=profile.page_id
    )

    assert reply is not None
    # Verify no commercial catalog delusions (sofas, coffee tables, armchairs, beds)
    assert "sofa" not in str(reply).lower()
    assert "coffee table" not in str(reply).lower()
    assert "armchair" not in str(reply).lower()
