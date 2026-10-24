"""Page-Specific AI Training & Study Endpoints (FR-AI-PAGE-01).

Enables merchants/campaign managers to:
1. View all integrated social pages (Facebook, Instagram) and their AI study status.
2. Trigger an AI deep-study to analyze the page's domain (e.g. Political Campaign like BallotBuzz).
3. Train/configure the AI model specifically for that page (Persona, System Instructions, Tone, Dos & Don'ts).
4. Guard against delusional responses (e.g. stops political campaigns from hallucinating retail products/sofas).
5. Manage page-specific knowledge items and simulate live chats.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.ai_knowledge import AIKnowledgeItem, KnowledgeCategory
from app.models.integration import Integration, IntegrationStatus
from app.models.page_ai_profile import PageAIProfile
from app.models.team_member import TeamMember, TeamRole
from app.schemas.ai_knowledge import KnowledgeItemOut
from app.schemas.page_ai import (
    PageAIProfileOut,
    PageAIProfileUpdate,
    PageKnowledgeCreate,
    PageSimulateChatRequest,
    PageSimulateChatResponse,
    PageStudyTriggerRequest,
)
from app.services.page_study_service import (
    fetch_meta_page_metadata,
    ingest_page_posts_as_knowledge,
    study_and_sync_page_profile,
)
from app.services.rag_service import index_knowledge_item

router = APIRouter(prefix="/ai/pages", tags=["page-ai-training"])


def _discover_shop_pages(db: Session, shop_id: uuid.UUID) -> list[dict[str, Any]]:
    """Inspect connected integrations (Facebook, Instagram) to find all active pages."""
    integrations = (
        db.query(Integration)
        .filter(
            Integration.shop_id == shop_id,
            Integration.provider.in_(["facebook", "instagram"]),
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .all()
    )

    discovered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for integ in integrations:
        cfg = integ.config or {}
        # 1. Main configured page
        if cfg.get("page_id") and str(cfg["page_id"]) not in seen_ids:
            pid = str(cfg["page_id"])
            seen_ids.add(pid)
            discovered.append({
                "page_id": pid,
                "page_name": cfg.get("page_name") or "Connected Page",
                "platform": integ.provider,
                "category": cfg.get("category") or "Business",
                "access_token": cfg.get("page_access_token"),
            })

        # 2. Multi-pages list
        for p in cfg.get("pages") or []:
            pid = str(p.get("id"))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                discovered.append({
                    "page_id": pid,
                    "page_name": p.get("name") or "Facebook Page",
                    "platform": "facebook",
                    "category": p.get("category") or "Business",
                    "access_token": p.get("access_token"),
                })

        # 3. Instagram business accounts
        for a in cfg.get("accounts") or []:
            aid = str(a.get("id"))
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                discovered.append({
                    "page_id": aid,
                    "page_name": a.get("name") or a.get("username") or "Instagram Account",
                    "platform": "instagram",
                    "category": "Creator",
                    "access_token": a.get("page_access_token"),
                })

    return discovered


@router.get("", response_model=list[PageAIProfileOut])
def list_page_ai_profiles(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> list[PageAIProfileOut]:
    """List all integrated pages with their AI study status & profile.

    Auto-registers any newly integrated pages so they are immediately available for study & training.
    """
    discovered_pages = _discover_shop_pages(db, current_user.shop_id)

    # Sync any discovered pages into PageAIProfile table
    for p in discovered_pages:
        existing = (
            db.query(PageAIProfile)
            .filter(
                PageAIProfile.shop_id == current_user.shop_id,
                PageAIProfile.page_id == p["page_id"],
            )
            .first()
        )
        if existing is None:
            new_profile = PageAIProfile(
                shop_id=current_user.shop_id,
                page_id=p["page_id"],
                platform=p["platform"],
                page_name=p["page_name"],
                page_category=p.get("category"),
                study_status="not_studied",
                ai_persona_name=f"{p['page_name']} Assistant",
                tone="Professional & Helpful",
                key_topics=["Inquiries", "Information"],
            )
            db.add(new_profile)

    db.commit()

    from app.models.page_permission import PageUserPermission

    query = db.query(PageAIProfile).filter(PageAIProfile.shop_id == current_user.shop_id)

    # System Admin (Product Owner) has master access to all pages
    is_super_admin = current_user.role == TeamRole.SUPER_ADMIN
    if not is_super_admin:
        # Rule: Invisible pages are hidden from everyone
        query = query.filter(PageAIProfile.is_visible.is_(True))

        # Rule: Visible pages only shown if user has explicit permission
        permitted_page_ids = [
            row[0]
            for row in db.query(PageUserPermission.page_id)
            .filter(
                PageUserPermission.user_id == current_user.id,
                PageUserPermission.can_view.is_(True),
            )
            .all()
        ]
        query = query.filter(PageAIProfile.page_id.in_(permitted_page_ids))

    profiles = query.order_by(PageAIProfile.updated_at.desc()).all()
    return profiles


@router.get("/{page_id}", response_model=PageAIProfileOut)
def get_page_ai_profile(
    page_id: str,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> PageAIProfileOut:
    profile = (
        db.query(PageAIProfile)
        .filter(
            PageAIProfile.shop_id == current_user.shop_id,
            PageAIProfile.page_id == page_id,
        )
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page AI profile not found")

    is_super_admin = current_user.role == TeamRole.SUPER_ADMIN
    if not is_super_admin:
        if not getattr(profile, "is_visible", True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page is not available")

        from app.models.page_permission import PageUserPermission
        has_perm = (
            db.query(PageUserPermission)
            .filter(
                PageUserPermission.page_id == page_id,
                PageUserPermission.user_id == current_user.id,
                PageUserPermission.can_view.is_(True),
            )
            .first()
        )
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this page",
            )

    return profile


@router.post("/{page_id}/study", response_model=PageAIProfileOut)
def study_page_with_ai(
    page_id: str,
    payload: PageStudyTriggerRequest | None = None,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> PageAIProfileOut:
    """Fetch page information from Meta Graph API, study it with AI, and generate a tailored profile."""
    # Find page name and token from integrations
    discovered = _discover_shop_pages(db, current_user.shop_id)
    target = next((p for p in discovered if p["page_id"] == page_id), None)

    profile = (
        db.query(PageAIProfile)
        .filter(
            PageAIProfile.shop_id == current_user.shop_id,
            PageAIProfile.page_id == page_id,
        )
        .first()
    )

    page_name = target["page_name"] if target else (profile.page_name if profile else f"Page {page_id}")
    category = target.get("category") if target else (profile.page_category if profile else None)
    token = target.get("access_token") if target else None
    platform = target.get("platform", "facebook") if target else "facebook"

    profile = study_and_sync_page_profile(
        db=db,
        shop_id=current_user.shop_id,
        page_id=page_id,
        page_name=page_name,
        category=category,
        page_access_token=token,
        platform=platform,
    )
    return profile


@router.post("/{page_id}/train-from-posts")
def train_page_from_posts(
    page_id: str,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Pull this Page's recent Facebook posts and teach the AI any real
    items/prices/policies mentioned in them, without re-running the full
    persona study. Lets a merchant re-train the AI whenever they post about a
    new or restocked product, so a customer asking about it gets a real
    answer instead of "I don't have that information".
    """
    discovered = _discover_shop_pages(db, current_user.shop_id)
    target = next((p for p in discovered if p["page_id"] == page_id), None)
    token = target.get("access_token") if target else None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This page isn't connected with a valid access token, so its posts can't be fetched.",
        )

    meta = fetch_meta_page_metadata(page_id, token, posts_limit=25)
    posts = meta.get("recent_posts") or []
    created = ingest_page_posts_as_knowledge(db, current_user.shop_id, page_id, posts)

    return {
        "fetched_posts": len(posts),
        "new_facts_learned": created,
        "message": (
            f"Checked {len(posts)} recent post(s) and learned {created} new fact(s)."
            if posts
            else "No posts were returned for this page — check that it has public posts and the "
            "connection still has a valid access token (try reconnecting it under Integrations)."
        ),
    }


@router.patch("/{page_id}", response_model=PageAIProfileOut)
def update_page_ai_profile(
    page_id: str,
    payload: PageAIProfileUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> PageAIProfileOut:
    """Update custom AI training parameters for a specific page."""
    profile = (
        db.query(PageAIProfile)
        .filter(
            PageAIProfile.shop_id == current_user.shop_id,
            PageAIProfile.page_id == page_id,
        )
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page AI profile not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(profile, k, v)

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{page_id}/knowledge", response_model=list[KnowledgeItemOut])
def list_page_knowledge(
    page_id: str,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> list[KnowledgeItemOut]:
    """Retrieve knowledge items specifically trained for this page."""
    items = (
        db.query(AIKnowledgeItem)
        .filter(
            AIKnowledgeItem.shop_id == current_user.shop_id,
            AIKnowledgeItem.page_id == page_id,
        )
        .order_by(AIKnowledgeItem.created_at.desc())
        .all()
    )
    return items


@router.post("/{page_id}/knowledge", response_model=KnowledgeItemOut)
def add_page_knowledge(
    page_id: str,
    payload: PageKnowledgeCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> KnowledgeItemOut:
    """Train the AI with a new fact or FAQ specifically for this page."""
    try:
        cat_enum = KnowledgeCategory(payload.category)
    except Exception:
        cat_enum = KnowledgeCategory.SHOP_FACT

    item = AIKnowledgeItem(
        shop_id=current_user.shop_id,
        page_id=page_id,
        category=cat_enum,
        title=payload.title,
        content=payload.content,
        is_pending_approval=False,
    )
    db.add(item)
    db.flush()
    index_knowledge_item(db, item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{page_id}/knowledge/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page_knowledge(
    page_id: str,
    item_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """Remove a trained knowledge item for this page."""
    item = (
        db.query(AIKnowledgeItem)
        .filter(
            AIKnowledgeItem.id == item_id,
            AIKnowledgeItem.shop_id == current_user.shop_id,
            AIKnowledgeItem.page_id == page_id,
        )
        .first()
    )
    if item:
        db.delete(item)
        db.commit()


@router.post("/{page_id}/simulate-chat", response_model=PageSimulateChatResponse)
def simulate_page_chat(
    page_id: str,
    payload: PageSimulateChatRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> PageSimulateChatResponse:
    """Simulate a chat specifically as this page with its custom prompt & trained knowledge."""
    from app.api.v1.endpoints.ai import _answer_from_shop_knowledge

    profile = (
        db.query(PageAIProfile)
        .filter(
            PageAIProfile.shop_id == current_user.shop_id,
            PageAIProfile.page_id == page_id,
        )
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page AI profile not found")

    res = _answer_from_shop_knowledge(
        db, current_user.shop, payload.message, return_sources=True, page_id=page_id
    )
    reply, used_k, used_p = res  # type: ignore[misc]

    return PageSimulateChatResponse(
        reply=str(reply),
        persona=profile.ai_persona_name,
        detected_type=profile.detected_type,
        used_knowledge_count=len(used_k),
        used_products_count=len(used_p),
    )
