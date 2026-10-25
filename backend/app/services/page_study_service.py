"""Page Study & AI Persona Tuning Service.

Whenever a Facebook/Instagram or social page is integrated:
1. Fetches the page's profile, category, about, bio, mission, and recent posts from Meta Graph API.
2. Runs an AI deep-study to analyze the page's true mission, domain, and tone.
   (e.g., distinguishing a political campaign or advocacy page from an e-commerce retail shop).
3. Configures a tailored AI Persona, system instructions, guardrails (dos & don'ts),
   and starter knowledge items scoped specifically to that page.
4. Eliminates delusions (e.g. stops political campaigns from hallucinating sofas and beds).
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.llm import chat_completion
from app.models.ai_knowledge import AIKnowledgeItem, KnowledgeCategory
from app.models.page_ai_profile import PageAIProfile, PageAIType
from app.models.product import Product, ProductVariant
from app.services.rag_service import index_knowledge_item, index_product

logger = logging.getLogger(__name__)


def fetch_meta_page_metadata(
    page_id: str, page_access_token: str | None, posts_limit: int = 8
) -> dict[str, Any]:
    """Fetch profile info & recent posts from Meta Graph API."""
    data: dict[str, Any] = {
        "about": None,
        "bio": None,
        "mission": None,
        "category": None,
        "website": None,
        "recent_posts": [],
    }

    if not page_access_token or not page_id:
        return data

    base_url = settings.meta_graph_base_url.rstrip("/")

    # 1. Page Details
    try:
        resp = httpx.get(
            f"{base_url}/{page_id}",
            params={
                "access_token": page_access_token,
                "fields": "id,name,about,description,bio,category,category_list,website,mission,general_info",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            p_data = resp.json()
            data["about"] = p_data.get("about") or p_data.get("description") or p_data.get("general_info")
            data["bio"] = p_data.get("bio")
            data["mission"] = p_data.get("mission")
            data["category"] = p_data.get("category")
            data["website"] = p_data.get("website")
    except Exception as exc:
        logger.warning("Failed to fetch page profile from Meta Graph for %s: %s", page_id, exc)

    # 2. Page Feed / Posts
    try:
        feed_resp = httpx.get(
            f"{base_url}/{page_id}/feed",
            params={
                "access_token": page_access_token,
                "fields": "id,message,created_time,permalink_url",
                "limit": posts_limit,
            },
            timeout=10.0,
        )
        if feed_resp.status_code == 200:
            posts = feed_resp.json().get("data", [])
            # Keep the real permalink_url Meta returns for each post, scoped to this
            # exact connected page — never guessed/constructed, so a link trained from
            # here always points at an actual post on the page the seller selected.
            data["recent_posts"] = [
                {"message": p.get("message"), "permalink_url": p.get("permalink_url")}
                for p in posts
                if p.get("message")
            ]
        else:
            logger.warning(
                "Meta Graph feed fetch for page %s returned %s: %s",
                page_id, feed_resp.status_code, feed_resp.text[:300],
            )
    except Exception as exc:
        logger.warning("Failed to fetch page posts from Meta Graph for %s: %s", page_id, exc)

    return data


def ingest_page_posts_as_knowledge(
    db: Session, shop_id: uuid.UUID, page_id: str, posts: list[str | dict[str, Any]]
) -> int:
    """Turn each of the Page's own post captions into a searchable knowledge fact.

    A post often names real items, prices, and delivery terms directly in the
    caption (e.g. "T-shirt available, price 330", regional courier charges)
    that never show up in "About" and wouldn't otherwise be answerable —
    without this, the AI only knows whatever was manually typed in as a fact.
    Safe to call repeatedly: already-ingested posts (matched by exact content)
    are skipped, so re-running only picks up genuinely new posts.

    `posts` items are either a plain string (legacy/no link available) or a
    dict `{"message": ..., "permalink_url": ...}` from `fetch_meta_page_metadata`
    — when a permalink_url is present, it's the real URL Meta returned for that
    exact post on this exact connected page, stored alongside the fact so the
    AI can hand customers the actual post link instead of inventing one.
    """
    # Dedup in Python, not SQL exact-match, since stored content may now carry an
    # appended "Post link: ..." suffix the raw post_text won't have.
    existing_contents = [
        c
        for (c,) in db.query(AIKnowledgeItem.content)
        .filter(AIKnowledgeItem.shop_id == shop_id, AIKnowledgeItem.page_id == page_id)
        .all()
    ]

    created = 0
    for post in posts:
        if isinstance(post, dict):
            post_text = (post.get("message") or "").strip()
            permalink = (post.get("permalink_url") or "").strip() or None
        else:
            post_text = (post or "").strip()
            permalink = None
        if not post_text or len(post_text) < 8:
            continue
        if any(c == post_text or c.startswith(post_text + "\n\n") for c in existing_contents):
            continue
        content = f"{post_text}\n\nPost link: {permalink}" if permalink else post_text
        post_item = AIKnowledgeItem(
            shop_id=shop_id,
            page_id=page_id,
            category=KnowledgeCategory.SHOP_FACT,
            title=f"Facebook post: {post_text[:60].strip()}",
            content=content,
            is_pending_approval=False,
        )
        db.add(post_item)
        db.flush()
        index_knowledge_item(db, post_item)
        created += 1
    db.commit()
    return created


def _normalize_detected_type(raw_type: str | None) -> str:
    if not raw_type:
        return "general"
    val = str(raw_type).strip().lower()
    if any(k in val for k in ["political", "campaign", "vote", "election", "polit", "civic"]):
        return "political_campaign"
    if any(k in val for k in ["non_profit", "non-profit", "ngo", "charity", "cause", "foundation"]):
        return "non_profit"
    if any(k in val for k in ["ecommerce", "e-commerce", "retail", "shop", "store", "boutique", "business", "commercial"]):
        return "ecommerce"
    if any(k in val for k in ["media", "news", "press", "journal"]):
        return "media"
    if any(k in val for k in ["service", "services", "consulting", "agency"]):
        return "services"
    if any(k in val for k in ["creator", "influencer", "blogger", "artist"]):
        return "creator"
    if any(k in val for k in ["community"]):
        return "community"
    return "general"


def generate_page_study_with_ai(
    page_name: str,
    page_category: str | None,
    meta_details: dict[str, Any],
) -> dict[str, Any]:
    """Dynamically analyze the connected page's identity, content, and recent posts with AI.

    The model reads the actual name and live page content (about, bio, mission, posts)
    to autonomously determine the nature of the page (political, non-profit, retail, media, etc.)
    and configure a matching AI persona, instructions, and guardrails.
    """
    about = meta_details.get("about") or ""
    bio = meta_details.get("bio") or ""
    mission = meta_details.get("mission") or ""
    recent_posts = meta_details.get("recent_posts") or []
    post_messages = [
        (p.get("message") or "") if isinstance(p, dict) else (p or "") for p in recent_posts
    ]
    posts_text = "\n- ".join(m for m in post_messages[:6] if m) if post_messages else "(No public posts found)"

    page_content_summary = (
        f"Page Name: {page_name}\n"
        f"Category: {page_category or 'Unspecified'}\n"
        f"About / Description: {about}\n"
        f"Bio: {bio}\n"
        f"Mission: {mission}\n"
        f"Recent Posts Content:\n- {posts_text}"
    )

    system_prompt = (
        "You are an AI page analyst. Your job is to study a social media page's actual data "
        "(name, category, description, bio, mission, and recent posts) to understand its true nature and mission.\n\n"
        "Requirements:\n"
        "1. Study the page's actual purpose from its data. Is it a political campaign, public advocacy, "
        "e-commerce retail store, community initiative, news/media, personal brand, or service provider?\n"
        "2. If the page is CLEARLY NOT an e-commerce shop (e.g. a political campaign, advocacy group, candidate, "
        "or NGO with an explicit civic/charitable mission), set 'include_product_catalog': false, and explicitly "
        "instruct the AI in 'dos_and_donts' to NEVER mention products, prices, sofas, furniture, or shopping orders. "
        "Instead, focus entirely on the page's actual mission and topics.\n"
        "3. If the page IS a retail store, OR its nature is unclear/general (e.g. little or no About/bio text yet, "
        "a newly connected page), set 'include_product_catalog': true — this platform is built for online shops, "
        "so default to retail unless the page data clearly says otherwise.\n"
        "4. Extract 3-5 real topics and initial factual FAQs directly from the provided page data.\n\n"
        "Return STRICT JSON only (no markdown, no backticks):\n"
        "{\n"
        '  "detected_type": "political_campaign" | "ecommerce" | "media" | "non_profit" | "community" | "services" | "creator" | "general",\n'
        '  "ai_persona_name": "Dynamic Persona Title for this page",\n'
        '  "ai_role_description": "Clear role description reflecting the page mission",\n'
        '  "tone": "Tone of voice matching the page content",\n'
        '  "key_topics": ["Topic 1", "Topic 2", "Topic 3"],\n'
        '  "dos_and_donts": "Guardrails and boundaries based on the page nature",\n'
        '  "system_instructions": "Custom system prompt directives for this page",\n'
        '  "include_product_catalog": boolean,\n'
        '  "starter_faqs": [\n'
        '    {"title": "Question or Topic", "content": "Answer derived from page data", "category": "faq_policy"}\n'
        '  ]\n'
        "}"
    )

    try:
        reply = chat_completion(system_prompt, page_content_summary, max_tokens=750)
        cleaned = re.sub(r"^```(?:json)?\s*", "", reply.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        if isinstance(data, dict) and "detected_type" in data:
            data["detected_type"] = _normalize_detected_type(data.get("detected_type"))
            return data
    except Exception as exc:
        logger.warning("LLM page study parsing failed, using dynamic content fallback: %s", exc)

    # Dynamic fallback based purely on the page's own category and content
    category_lower = (page_category or "").lower()
    content_lower = f"{page_name} {about} {bio} {mission}".lower()

    is_political = any(w in category_lower or w in content_lower for w in ["polit", "campaign", "elect", "vote", "ballot", "democra"])
    is_ngo = any(
        w in category_lower or w in content_lower
        for w in [
            "non-profit", "nonprofit", "ngo", "charity", "foundation", "cause",
            "conservation", "environment", "advocacy", "humanitarian", "relief",
            "awareness", "wildlife", "sustainability",
        ]
    )
    is_store = any(w in category_lower or w in content_lower for w in ["shop", "store", "retail", "boutique", "market"])

    if is_political:
        detected_type = PageAIType.POLITICAL_CAMPAIGN.value
        persona = f"{page_name} Representative"
        role_desc = f"Official campaign and civic engagement assistant for {page_name}"
        tone = "Civic, Articulate, and Respectful"
        include_catalog = False
        dos_donts = (
            f"Focus on {page_name}'s platform, civic engagement, and public updates. "
            "Do NOT discuss or sell commercial products or take retail orders."
        )
    elif is_ngo:
        detected_type = PageAIType.NON_PROFIT.value
        persona = f"{page_name} Outreach Assistant"
        role_desc = f"Community and mission guide for {page_name}"
        tone = "Purpose-driven, Empathetic, and Informative"
        include_catalog = False
        dos_donts = (
            f"Represent {page_name}'s mission and community initiatives. "
            "Do NOT pitch commercial sales or retail products."
        )
    elif is_store:
        detected_type = PageAIType.ECOMMERCE.value
        persona = f"{page_name} Sales Assistant"
        role_desc = f"Customer support and sales assistant for {page_name}"
        tone = "Helpful, Friendly, and Professional"
        include_catalog = True
        dos_donts = "Help customers find items, check stock, and place orders accurately."
    else:
        # No strong political/non-profit/retail signal in the page's own data (common for a
        # freshly connected page with little About/bio filled in yet). This platform is built
        # for online shops, so default new/ambiguous pages to retail rather than silently
        # refusing to ever mention products — a shop owner connecting a page expects the AI
        # to be able to answer "do you have X" as soon as products are added or synced.
        detected_type = PageAIType.GENERAL.value
        persona = f"{page_name} Assistant"
        role_desc = f"Customer support and sales assistant for {page_name}"
        tone = "Professional and Helpful"
        include_catalog = True
        dos_donts = "Help customers find items, check stock, and place orders accurately based on verified facts."

    topics = [t.strip() for t in (about or page_category or "Information").split(",") if t.strip()][:4]
    if not topics:
        topics = ["Inquiries", "Updates"]

    return {
        "detected_type": detected_type,
        "ai_persona_name": persona,
        "ai_role_description": role_desc,
        "tone": tone,
        "key_topics": topics,
        "dos_and_donts": dos_donts,
        "system_instructions": f"Represent {page_name} with clear, professional communication reflecting its mission.",
        "include_product_catalog": include_catalog,
        "starter_faqs": [
            {
                "title": f"About {page_name}",
                "content": about or bio or mission or f"Welcome to {page_name}. We are here to provide information and assist with inquiries.",
                "category": "shop_fact",
            }
        ],
    }


def study_and_sync_page_profile(
    db: Session,
    shop_id: uuid.UUID,
    page_id: str,
    page_name: str,
    category: str | None = None,
    page_access_token: str | None = None,
    platform: str = "facebook",
) -> PageAIProfile:
    """Core entry point to study a page with AI and save its profile & starter knowledge."""
    profile = (
        db.query(PageAIProfile)
        .filter(PageAIProfile.shop_id == shop_id, PageAIProfile.page_id == page_id)
        .first()
    )
    if profile is None:
        profile = PageAIProfile(
            shop_id=shop_id,
            page_id=page_id,
            platform=platform,
            page_name=page_name,
            page_category=category,
            study_status="studying",
        )
        db.add(profile)
        db.flush()

    # Starter FAQs are a one-time seed, not something to regenerate on every
    # re-study — otherwise re-running "Study Page with AI" (or an LLM call
    # that phrases things slightly differently each time) keeps piling up
    # near-duplicate knowledge items.
    already_studied_before = profile.study_status == "studied"

    profile.study_status = "studying"
    profile.page_name = page_name
    if category:
        profile.page_category = category

    # 1. Fetch live page data from Meta Graph API
    meta_meta = fetch_meta_page_metadata(page_id, page_access_token)
    profile.about = meta_meta.get("about") or profile.about
    profile.bio = meta_meta.get("bio") or profile.bio
    profile.mission = meta_meta.get("mission") or profile.mission
    profile.website = meta_meta.get("website") or profile.website
    profile.raw_study_data = meta_meta

    # 2. Run AI study
    study_res = generate_page_study_with_ai(page_name, category or profile.page_category, meta_meta)

    profile.detected_type = study_res.get("detected_type", "general")
    profile.ai_persona_name = study_res.get("ai_persona_name", f"{page_name} Assistant")
    profile.ai_role_description = study_res.get("ai_role_description")
    profile.tone = study_res.get("tone", "Professional & Helpful")
    profile.key_topics = study_res.get("key_topics", [])
    profile.dos_and_donts = study_res.get("dos_and_donts")
    profile.system_instructions = study_res.get("system_instructions")
    profile.include_product_catalog = bool(study_res.get("include_product_catalog", False))
    profile.study_status = "studied"
    profile.last_studied_at = datetime.datetime.utcnow()

    db.add(profile)
    db.flush()

    # 3. Seed starter page-specific knowledge items — ONCE, on first study only.
    # These are meant as an initial seed the merchant can edit/delete; re-running
    # "Study Page with AI" later must never pile up near-duplicate copies of them
    # (an LLM can phrase the exact same fact slightly differently each call, so
    # even an exact-title dedup check can be bypassed).
    starter_faqs = (study_res.get("starter_faqs") or []) if not already_studied_before else []
    existing_titles_norm = {
        (t or "").strip().casefold()
        for (t,) in db.query(AIKnowledgeItem.title).filter(
            AIKnowledgeItem.shop_id == shop_id, AIKnowledgeItem.page_id == page_id
        )
    }
    for faq in starter_faqs:
        title = faq.get("title") or f"About {page_name}"
        if title.strip().casefold() in existing_titles_norm:
            continue
        existing_titles_norm.add(title.strip().casefold())

        cat_val = faq.get("category", "faq_policy")
        try:
            cat_enum = KnowledgeCategory(cat_val)
        except Exception:
            cat_enum = KnowledgeCategory.FAQ_POLICY

        k_item = AIKnowledgeItem(
            shop_id=shop_id,
            page_id=page_id,
            category=cat_enum,
            title=title,
            content=faq.get("content") or "",
            is_pending_approval=False,
        )
        db.add(k_item)
        db.flush()
        index_knowledge_item(db, k_item)

    # 3b. Ingest the Page's own recent posts as searchable facts.
    ingest_page_posts_as_knowledge(db, shop_id, page_id, meta_meta.get("recent_posts") or [])

    db.commit()

    # 4. If this is a retail page but IT specifically has no products of its own
    # yet, pull the Page's own commerce catalog so the AI has real items/prices
    # to quote for THIS page instead of saying "I don't have that information"
    # for everything. Checked per-page (not shop-wide) so a shop running
    # several pages still gets each page's own catalog synced independently —
    # one page already having products must never block another page's sync.
    if profile.include_product_catalog and page_access_token:
        has_own_products = (
            db.query(Product.id).filter(Product.shop_id == shop_id, Product.page_id == page_id).first()
            is not None
        )
        if not has_own_products:
            try:
                _sync_page_catalog_into_products(db, shop_id, page_id, page_access_token)
            except Exception as exc:
                logger.warning("Auto catalog sync from page '%s' failed: %s", page_id, exc)

    db.refresh(profile)
    logger.info("Studied page '%s' (%s) -> Type: %s", page_name, page_id, profile.detected_type)
    return profile


def _sync_page_catalog_into_products(
    db: Session, shop_id: uuid.UUID, page_id: str, page_access_token: str
) -> int:
    """Pull the connected Page's commerce catalog and create+index shop Products from it."""
    from app.integrations.meta_graph import list_page_catalog_items, normalize_catalog_item

    raw_items = list_page_catalog_items(page_id, page_access_token)
    created = 0
    for raw in raw_items:
        item = normalize_catalog_item(raw)
        if not item["name"]:
            continue
        existing = (
            db.query(Product)
            .filter(Product.shop_id == shop_id, Product.page_id == page_id, Product.name == item["name"])
            .first()
        )
        if existing:
            continue
        product = Product(
            shop_id=shop_id,
            page_id=page_id,
            name=item["name"],
            price=item["price"] or 0,
            description=item.get("description"),
            photo_url=item.get("photo_url"),
            kind="product",
            category="facebook_sync",
        )
        product.variants = [ProductVariant(attributes={"size": "default"}, stock_qty=0, reorder_point=2)]
        db.add(product)
        db.flush()
        index_product(db, product)
        created += 1
    db.commit()
    return created
