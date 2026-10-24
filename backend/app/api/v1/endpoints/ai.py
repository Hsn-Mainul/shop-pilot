import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import settings
from app.db.session import get_db
from app.integrations.llm import (
    LLMNotConfiguredError,
    build_shop_system_prompt,
    chat_completion,
    generate_social_caption,
)
from app.models.ai_knowledge import AIKnowledgeItem
from app.models.integration import DialectPack
from app.models.product import Product
from app.models.team_member import TeamMember, TeamRole
from app.schemas.ai_knowledge import (
    AskRequest,
    AskResponse,
    KnowledgeItemCreate,
    KnowledgeItemOut,
    RagReindexResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagStatusResponse,
    SocialCaptionRequest,
    SocialCaptionResponse,
)
from app.schemas.voice_config import (
    SimulateCallRequest,
    SimulateCallResponse,
    SimulateChatRequest,
    SimulateChatResponse,
)
from app.services.ai_credits import consume_text_credit, consume_voice_minutes, module_enabled
from app.services.rag_service import (
    get_grounded_rag_context,
    index_knowledge_item,
    reindex_shop_knowledge_and_catalog,
    search_knowledge_and_catalog,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/knowledge", response_model=list[KnowledgeItemOut])
def list_knowledge(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[KnowledgeItemOut]:
    return (
        db.query(AIKnowledgeItem)
        .filter(AIKnowledgeItem.shop_id == current_user.shop_id, AIKnowledgeItem.is_pending_approval.is_(False))
        .all()
    )


@router.post("/knowledge", response_model=KnowledgeItemOut, status_code=status.HTTP_201_CREATED)
def teach_knowledge(
    payload: KnowledgeItemCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> KnowledgeItemOut:
    item = AIKnowledgeItem(shop_id=current_user.shop_id, is_pending_approval=False, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)

    # Immediately index into vector space with Ollama
    try:
        index_knowledge_item(db, item)
        db.refresh(item)
    except Exception:
        pass

    return item


@router.get("/knowledge/pending", response_model=list[KnowledgeItemOut])
def list_pending_knowledge(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[KnowledgeItemOut]:
    return (
        db.query(AIKnowledgeItem)
        .filter(AIKnowledgeItem.shop_id == current_user.shop_id, AIKnowledgeItem.is_pending_approval.is_(True))
        .all()
    )


@router.post("/knowledge/pending/{item_id}/approve", response_model=KnowledgeItemOut | None)
def approve_pending_knowledge(
    item_id: uuid.UUID,
    approve: bool = True,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> KnowledgeItemOut | None:
    item = (
        db.query(AIKnowledgeItem)
        .filter(AIKnowledgeItem.id == item_id, AIKnowledgeItem.shop_id == current_user.shop_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found")
    if not approve:
        db.delete(item)
        db.commit()
        return None
    item.is_pending_approval = False
    db.add(item)
    db.commit()
    db.refresh(item)

    try:
        index_knowledge_item(db, item)
        db.refresh(item)
    except Exception:
        pass

    return item


def _answer_from_shop_knowledge(
    db: Session,
    shop: Any,
    message: str,
    return_sources: bool = False,
    page_id: str | None = None,
    history: str = "",
) -> str | tuple[str, list[uuid.UUID], list[uuid.UUID]]:
    """FR-AI-01: scoped strictly to this Shop's own taught facts/FAQs and live catalog.

    Supports Page-specific AI training (e.g. BallotBuzz political campaign vs retail store).
    Uses Ollama vector search (RAG) to retrieve top matching facts and catalog
    items, minimizing prompt size and eliminating hallucination.
    """
    from app.integrations.llm import build_page_system_prompt
    from app.models.page_ai_profile import PageAIProfile

    page_profile: PageAIProfile | None = None
    include_products = True

    if page_id:
        page_profile = (
            db.query(PageAIProfile)
            .filter(PageAIProfile.shop_id == shop.id, PageAIProfile.page_id == page_id)
            .first()
        )
        if page_profile:
            include_products = page_profile.include_product_catalog

    snippets, used_k_ids, used_p_ids = get_grounded_rag_context(
        db, shop, message, page_id=page_id, include_products=include_products
    )

    try:
        if page_profile and page_profile.is_active:
            system_prompt = build_page_system_prompt(page_profile, snippets)
        else:
            system_prompt = build_shop_system_prompt(shop.name, snippets)

        # Recent turns of this same conversation, so the AI remembers what the
        # customer already said (item, phone, address) instead of asking again
        # on every message — only affects what the model SEES, not the RAG
        # search query above, so retrieval relevance isn't diluted by old text.
        user_message = f"{history}\nCustomer (latest message): {message}" if history else message
        reply = chat_completion(system_prompt, user_message)
        if return_sources:
            return reply, used_k_ids, used_p_ids
        return reply
    except LLMNotConfiguredError:
        # Graceful fallback when no LLM is configured
        k_query = db.query(AIKnowledgeItem).filter(
            AIKnowledgeItem.shop_id == shop.id,
            AIKnowledgeItem.is_pending_approval.is_(False),
        )
        if page_id:
            k_query = k_query.filter(
                (AIKnowledgeItem.page_id == page_id) | (AIKnowledgeItem.page_id.is_(None))
            )
        knowledge_items = k_query.all()
        matched = next((s for s in knowledge_items if message.lower() in s.content.lower()), None)
        fallback = (
            matched.content
            if matched
            else "I don't have that information yet — an LLM isn't configured, so I can only match exact taught facts."
        )
        if return_sources:
            return fallback, ([matched.id] if matched else []), []
        return fallback


@router.post("/ask", response_model=AskResponse)
def ask_assistant(
    payload: AskRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> AskResponse:
    if not module_enabled(current_user.shop, "conversations", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI conversations module is off")
    if not consume_text_credit(db, current_user.shop_id, reason="ai_ask"):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="AI text credits exhausted")

    res = _answer_from_shop_knowledge(db, current_user.shop, payload.question, return_sources=True)
    db.commit()
    answer, used_k, used_p = res  # type: ignore[misc]
    return AskResponse(answer=answer, used_knowledge_item_ids=used_k, used_product_ids=used_p)


@router.post("/social-caption", response_model=SocialCaptionResponse)
def generate_social_post_caption(
    payload: SocialCaptionRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> SocialCaptionResponse:
    """Write a caption/hashtags that reflects the attached photo and matches
    the connected page's own persona/tone, instead of guessing from text alone."""
    if not consume_text_credit(db, current_user.shop_id, reason="social_caption", page_id=payload.page_id):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="AI text credits exhausted")

    language_rule = (
        "Write entirely in Bangla (বাংলা script). Do not use English except for brand names."
        if payload.language == "bn"
        else "Write entirely in English."
    )

    page_persona = page_tone = page_detected_type = None
    if payload.page_id:
        from app.models.page_ai_profile import PageAIProfile

        profile = (
            db.query(PageAIProfile)
            .filter(PageAIProfile.shop_id == current_user.shop_id, PageAIProfile.page_id == payload.page_id)
            .first()
        )
        if profile:
            page_persona = profile.page_name
            page_tone = profile.tone
            page_detected_type = profile.detected_type

    product_text = None
    if payload.product_id:
        product = (
            db.query(Product)
            .filter(Product.id == payload.product_id, Product.shop_id == current_user.shop_id)
            .first()
        )
        if product:
            product_text = f"{product.name}" + (f", {product.category}" if product.category else "")
            product_text += f", priced {product.price} {current_user.shop.currency or 'BDT'}"

    image_bytes = None
    used_image = False
    if payload.photo_url:
        from app.services.media_resolver import resolve_photo_bytes

        resolved = resolve_photo_bytes(payload.photo_url)
        if resolved:
            image_bytes, _ = resolved
            used_image = True

    answer = generate_social_caption(
        kind=payload.kind,
        language_rule=language_rule,
        page_persona=page_persona,
        page_tone=page_tone,
        page_detected_type=page_detected_type,
        product_text=product_text,
        user_context=payload.context,
        image_bytes=image_bytes,
    )
    db.commit()
    return SocialCaptionResponse(answer=answer, used_image=used_image)


@router.post("/simulate-chat", response_model=SimulateChatResponse)
def simulate_chat(
    payload: SimulateChatRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> SimulateChatResponse:
    """FR-AI-05: test the AI's behavior before enabling Autopilot — uses Ollama RAG + chat."""
    if not module_enabled(current_user.shop, "studio", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI studio module is off")
    if not consume_text_credit(db, current_user.shop_id, reason="simulate_chat"):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="AI text credits exhausted")
    reply = _answer_from_shop_knowledge(db, current_user.shop, payload.message)
    db.commit()
    return SimulateChatResponse(reply=str(reply))


@router.post("/simulate-call", response_model=SimulateCallResponse)
def simulate_call(
    payload: SimulateCallRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> SimulateCallResponse:
    """FR-VPER-03: preview the opening script + dialect; optionally warm TTS cache."""
    from app.integrations.tts import TTSNotConfiguredError, synthesize_to_file
    from app.models.voice_config import VoicePersona

    dialect = None
    if payload.dialect_code:
        dialect = db.query(DialectPack).filter(DialectPack.language_code == payload.dialect_code).first()
        if dialect is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown dialect code")

    persona = db.query(VoicePersona).filter(VoicePersona.shop_id == current_user.shop_id).first()
    shop_name = current_user.shop.name
    opening = (
        payload.opening_message
        or (persona.opening_script if persona and persona.opening_script else None)
        or f"Hello, thank you for calling {shop_name}. How can I help you today?"
    )
    if shop_name.lower() not in opening.lower():
        opening = f"{opening} You are speaking with {shop_name}."

    if not module_enabled(current_user.shop, "voice", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI voice module is off")
    consume_voice_minutes(db, current_user.shop_id, minutes=0.1, reason="simulate_call")

    tts_ready = False
    if settings.llm_api_key:
        try:
            synthesize_to_file(opening, voice_name=(persona.voice_name if persona else "default_bn_female"))
            tts_ready = True
        except TTSNotConfiguredError:
            tts_ready = False

    db.commit()
    return SimulateCallResponse(
        transcript_preview=opening,
        dialect_used=dialect.language_code if dialect else "bn-STD",
        tts_ready=tts_ready,
    )


# --- RAG & Ollama Management Endpoints ---


@router.get("/rag/status", response_model=RagStatusResponse)
def get_rag_status(
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> RagStatusResponse:
    """Check Ollama service status, installed models, and local vector index coverage."""
    from app.integrations.ollama import check_ollama_status
    from app.models.product import Product

    ollama_info = check_ollama_status()

    # Total and indexed knowledge items
    k_items = (
        db.query(AIKnowledgeItem)
        .filter(
            AIKnowledgeItem.shop_id == current_user.shop_id,
            AIKnowledgeItem.is_pending_approval.is_(False),
        )
        .all()
    )
    k_indexed = sum(1 for k in k_items if k.embedding)

    # Total and indexed products
    prods = db.query(Product).filter(Product.shop_id == current_user.shop_id).all()
    p_indexed = sum(1 for p in prods if p.embedding)

    return RagStatusResponse(
        ollama_online=bool(ollama_info.get("online")),
        ollama_version=ollama_info.get("version"),
        chat_model=ollama_info.get("chat_model") or settings.ollama_chat_model,
        chat_ready=bool(ollama_info.get("chat_ready")),
        embed_model=ollama_info.get("embed_model") or settings.ollama_embed_model,
        embed_ready=bool(ollama_info.get("embed_ready")),
        knowledge_indexed=k_indexed,
        knowledge_total=len(k_items),
        products_indexed=p_indexed,
        products_total=len(prods),
        models_available=ollama_info.get("models") or [],
    )


@router.post("/rag/reindex", response_model=RagReindexResponse)
def reindex_rag(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> RagReindexResponse:
    """Rebuild all embeddings for shop facts and catalog products via Ollama."""
    stats = reindex_shop_knowledge_and_catalog(db, current_user.shop_id)
    return RagReindexResponse(
        shop_id=stats["shop_id"],
        indexed_knowledge_count=stats["indexed_knowledge_count"],
        total_knowledge_count=stats["total_knowledge_count"],
        indexed_products_count=stats["indexed_products_count"],
        total_products_count=stats["total_products_count"],
        message=(
            f"Successfully vectorized {stats['indexed_knowledge_count']}/{stats['total_knowledge_count']} shop facts "
            f"and {stats['indexed_products_count']}/{stats['total_products_count']} catalog items with Ollama."
        ),
    )


@router.post("/rag/search", response_model=RagSearchResponse)
def test_rag_search(
    payload: RagSearchRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> RagSearchResponse:
    """Test semantic vector search directly across knowledge base and product catalog."""
    res = search_knowledge_and_catalog(
        db,
        current_user.shop_id,
        payload.query,
        top_k_knowledge=payload.top_k,
        top_k_products=payload.top_k,
    )
    return RagSearchResponse(
        query=payload.query,
        mode=res.get("mode", "vector"),
        knowledge=res.get("knowledge", []),
        products=res.get("products", []),
    )
