"""Multi-Tier Resilient LLM Orchestrator with Intelligent Failover.

Architectural Guarantees:
1. Priority-Driven: Always tries the most precise, high-parameter model first (e.g. Groq 120B/27B,
   OpenAI, Gemini) for fluent native Bengali and precise domain replies.
2. Intelligent Failover & Circuit Breaker: If any model is busy, rate-limited (429), overloaded (503),
   or times out, it immediately fails over to the next available tier without interrupting the chat.
3. Local Fallback: If cloud providers are unavailable, gracefully falls back to local Ollama.
4. Clean Presentation: Enforces zero emojis and human-readable formatting.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory circuit breaker tracking: candidate_name -> unix timestamp until which candidate is marked busy
_CANDIDATE_BUSY_UNTIL: dict[str, float] = {}
BUSY_BACKOFF_SECONDS = 60.0


class LLMNotConfiguredError(RuntimeError):
    pass


@dataclass
class LLMCandidate:
    name: str
    url: str
    model: str
    api_key: str | None
    timeout: float = 15.0
    is_reasoning_model: bool = False


def _get_ordered_llm_candidates() -> list[LLMCandidate]:
    """Build candidate list ordered from most precise/capable to local fallback."""
    candidates: list[LLMCandidate] = []

    # 1. High-precision Cloud: Groq Primary (e.g. openai/gpt-oss-120b or llama-3.3-70b)
    groq_key = settings.effective_groq_api_key
    if groq_key:
        groq_model = settings.effective_groq_model
        def _is_reasoning_model(model_name: str) -> bool:
            lowered = model_name.lower()
            return "gpt-oss-120b" in lowered or "reasoning" in lowered or "qwen3" in lowered

        candidates.append(
            LLMCandidate(
                name="groq_primary",
                url="https://api.groq.com/openai/v1/chat/completions",
                model=groq_model,
                api_key=groq_key,
                timeout=18.0,
                is_reasoning_model=_is_reasoning_model(groq_model),
            )
        )
        # 2. Secondary Cloud: Groq Fast/Multilingual backup (qwen/qwen3.8-27b)
        backup_model = settings.groq_backup_model
        if backup_model and backup_model != groq_model:
            candidates.append(
                LLMCandidate(
                    name="groq_backup",
                    url="https://api.groq.com/openai/v1/chat/completions",
                    model=backup_model,
                    api_key=groq_key,
                    timeout=14.0,
                    is_reasoning_model=_is_reasoning_model(backup_model),
                )
            )

    # 3. OpenAI (if key provided)
    if settings.openai_api_key:
        candidates.append(
            LLMCandidate(
                name="openai",
                url="https://api.openai.com/v1/chat/completions",
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                timeout=15.0,
            )
        )

    # 4. Google Gemini (via OpenAI-compatible endpoint)
    if settings.gemini_api_key:
        candidates.append(
            LLMCandidate(
                name="gemini",
                url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                model=settings.gemini_model,
                api_key=settings.gemini_api_key,
                timeout=15.0,
            )
        )

    # 5. Custom configured OpenAI-compatible gateway (if explicit and not Ollama)
    if settings.llm_api_key and not settings.is_ollama:
        candidates.append(
            LLMCandidate(
                name="custom_llm",
                url=f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                timeout=20.0,
            )
        )

    # 6. Local Ollama (always available when service is running locally)
    ollama_url = f"{settings.ollama_base_url.rstrip('/')}/v1/chat/completions"
    candidates.append(
        LLMCandidate(
            name="ollama_local",
            url=ollama_url,
            model=settings.ollama_chat_model,
            api_key=None,
            timeout=75.0,
        )
    )

    return candidates


def _clean_output_text(text: str) -> str:
    """Clean markdown artifacts and strip emojis for a professional, clean tone."""
    if not text:
        return ""
    # Strip non-text emoji symbols
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    # Remove any stray system tags
    cleaned = re.sub(r"<(?:think|reasoning)>.*?</(?:think|reasoning)>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def chat_completion(system_prompt: str, user_message: str, *, max_tokens: int = 500) -> str:
    """Execute chat completion across prioritized candidate tiers with automatic failover."""
    candidates = _get_ordered_llm_candidates()
    if not candidates:
        raise LLMNotConfiguredError("No LLM candidates available in configuration.")

    now = time.time()
    # Check if all candidates are marked busy; if so, reset circuit breakers to give candidates a fresh try
    all_busy = all(now < _CANDIDATE_BUSY_UNTIL.get(c.name, 0) for c in candidates)
    if all_busy:
        logger.info("All LLM candidates were marked busy. Resetting circuit breakers to retry.")
        _CANDIDATE_BUSY_UNTIL.clear()

    errors_encountered: list[str] = []

    for candidate in candidates:
        busy_until = _CANDIDATE_BUSY_UNTIL.get(candidate.name, 0)
        if now < busy_until:
            logger.info(
                "Skipping busy candidate '%s' (cooling down for %.1fs)",
                candidate.name,
                busy_until - now,
            )
            continue

        headers: dict[str, str] = {}
        if candidate.api_key:
            headers["Authorization"] = f"Bearer {candidate.api_key}"

        # If calling a reasoning model, allow higher token budget so reasoning doesn't truncate the reply
        effective_max_tokens = max(max_tokens, 600) if candidate.is_reasoning_model else max_tokens

        request_body: dict[str, Any] = {
            "model": candidate.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": effective_max_tokens,
        }
        if candidate.is_reasoning_model and candidate.name.startswith("groq"):
            # Groq keeps chain-of-thought out of `content` for these models when asked to.
            request_body["reasoning_format"] = "hidden"

        try:
            logger.debug("Dispatching LLM request to candidate '%s' (model: %s)", candidate.name, candidate.model)
            response = httpx.post(
                candidate.url,
                headers=headers,
                json=request_body,
                timeout=candidate.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content") or ""
                    # If content is empty but model provided reasoning, extract conclusion or text
                    if not content and candidate.is_reasoning_model:
                        content = msg.get("reasoning") or ""

                    cleaned = _clean_output_text(content)
                    if cleaned:
                        logger.info("LLM candidate '%s' (%s) succeeded", candidate.name, candidate.model)
                        return cleaned

            # Non-200 status code: mark busy and failover
            err_msg = f"HTTP {response.status_code}: {response.text[:120]}"
            logger.warning(
                "LLM candidate '%s' returned %s. Marking busy for %.0fs and failing over...",
                candidate.name,
                err_msg,
                BUSY_BACKOFF_SECONDS,
            )
            _CANDIDATE_BUSY_UNTIL[candidate.name] = time.time() + BUSY_BACKOFF_SECONDS
            errors_encountered.append(f"{candidate.name}: {err_msg}")

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError, Exception) as exc:
            logger.warning(
                "LLM candidate '%s' (%s) error: %s. Marking busy for %.0fs and failing over...",
                candidate.name,
                candidate.model,
                exc,
                BUSY_BACKOFF_SECONDS,
            )
            _CANDIDATE_BUSY_UNTIL[candidate.name] = time.time() + BUSY_BACKOFF_SECONDS
            errors_encountered.append(f"{candidate.name}: {exc}")

    # If all candidates failed:
    raise LLMNotConfiguredError(f"All LLM tiers failed or are busy. Details: {'; '.join(errors_encountered)}")


def build_shop_system_prompt(shop_name: str, knowledge_snippets: list[str]) -> str:
    """FR-AI-01: the assistant must answer strictly from this Shop's own data."""
    facts = "\n".join(f"- {s}" for s in knowledge_snippets) or "(no shop facts taught yet)"
    return (
        f"You are the professional AI sales & customer support assistant for '{shop_name}'.\n"
        f"Key Instructions:\n"
        f"1. Language & Tone: If the message explicitly tells you which language to write in (e.g. "
        f"'Write entirely in English' or 'Write entirely in Bangla'), you MUST follow that instruction "
        f"exactly and ignore any other language cues in the message. Otherwise, answer naturally and "
        f"eloquently in the exact language the customer uses (Standard Bangla বাংলা, Banglish/Romanized "
        f"Bangla, or English). Never use broken or distorted script.\n"
        f"2. Live Catalog & Pricing: Quote only the exact prices, sizes, and stock quantities provided in the Shop facts, "
        f"copying the currency symbol/code exactly as shown there (e.g. '৳499 (BDT)') — never substitute a different "
        f"currency symbol such as ₹ or $. Never guess or hallucinate unlisted products or prices.\n"
        f"3. Chat-to-Order & Memory: The conversation so far (if shown above the latest message) is real — read it "
        f"before replying. If the customer already gave the item, quantity, phone number, or delivery address in an "
        f"earlier message, do NOT ask for it again; only ask for whatever is still missing. Once item, quantity, "
        f"phone, and address are all known, tell the customer their order is being placed — a separate system will "
        f"confirm it with a reference number right after your reply.\n"
        f"4. Shop Policies: Answer delivery fees, COD (Cash on Delivery), return policies, and opening hours strictly based on the facts below.\n"
        f"5. Hallucination Control: If any detail is not covered in the facts below, politely state that you do not have that specific information.\n\n"
        f"Shop Facts & Live Data:\n{facts}"
    )


def build_page_system_prompt(page_profile: Any, knowledge_snippets: list[str]) -> str:
    """Build a specialized, non-hallucinating system prompt for an integrated Page."""
    facts = "\n".join(f"- {s}" for s in knowledge_snippets) or "(no specific facts taught for this page yet)"

    topics = (
        ", ".join(page_profile.key_topics)
        if getattr(page_profile, "key_topics", None)
        else "Page initiatives and community engagement"
    )
    persona = getattr(page_profile, "ai_persona_name", None) or f"{page_profile.page_name} Assistant"
    role_desc = (
        getattr(page_profile, "ai_role_description", None)
        or f"Official representative for {page_profile.page_name}"
    )
    tone = getattr(page_profile, "tone", "Professional, Inspiring, and Courteous")
    custom_inst = (
        getattr(page_profile, "system_instructions", "")
        or f"Represent {page_profile.page_name} with clear, professional, and respectful communication."
    )
    dos_donts = (
        getattr(page_profile, "dos_and_donts", "")
        or "Be courteous, respectful, and answer questions accurately based on verified facts."
    )
    include_catalog = getattr(page_profile, "include_product_catalog", False)

    if include_catalog:
        catalog_rules = (
            "2. Live Catalog & Pricing: Quote exact items, prices, and quantities provided in the facts, copying the "
            "currency symbol/code exactly as shown there (e.g. '৳499 (BDT)') — never substitute a different currency "
            "symbol such as ₹ or $. Never hallucinate unlisted items.\n"
            "3. Chat-to-Order & Memory: The conversation so far (if shown above the latest message) is real — read it "
            "before replying. If the customer already gave the item, quantity, phone, or address earlier, do not ask "
            "again; only ask for what's still missing. Once all four are known, tell them their order is being "
            "placed — a separate system will confirm it with a reference number right after your reply.\n"
        )
    else:
        catalog_rules = (
            f"2. Scope & Boundaries: You represent '{page_profile.page_name}' "
            f"({page_profile.page_category or page_profile.detected_type}). "
            "DO NOT talk about selling commercial products, furniture, or asking for retail shipping addresses. "
            f"Focus entirely on: {topics}.\n"
        )

    return (
        f"You are {persona}, the {role_desc}.\n"
        f"Page: {page_profile.page_name} | Nature: {page_profile.page_category or page_profile.detected_type}\n"
        f"Tone of Voice: {tone}\n\n"
        f"Core Directives for this Page:\n"
        f"{custom_inst}\n\n"
        f"Key Rules:\n"
        f"1. Language & Precision: Answer naturally, fluently, and grammatically in the exact language used by the visitor "
        f"(Standard Bangla বাংলা, Banglish, or English). Never generate broken phonetic or distorted characters.\n"
        f"{catalog_rules}"
        f"3. Dos & Don'ts:\n{dos_donts}\n"
        f"4. Hallucination Control: Answer strictly using verified page facts. If any detail is unknown, "
        f"politely state that you do not have that specific information.\n\n"
        f"Verified Page Knowledge & Facts:\n{facts}"
    )


def _describe_photo(image_bytes: bytes) -> str | None:
    """Ask the local vision model for a short, plain factual description of
    the photo only — no persona, tone, language, or hashtag constraints.

    Small vision models (moondream) are reliable at this narrow task but
    degrade into repetition loops or ignore instructions when asked to also
    juggle persona/tone/language/product constraints in the same call. So we
    keep this call as simple as possible and let a capable text model handle
    all the constrained writing in a second step.
    """
    from app.integrations.ollama import generate_vision_text

    result = generate_vision_text(
        "Describe this photo in 1-2 plain factual sentences: the item(s), color, style, and setting. "
        "Do not write a caption or slogan, just describe what is visible.",
        image_bytes,
        max_tokens=80,
    )
    if not result:
        return None
    description = _clean_output_text(result)
    # Repetition-loop guard: a healthy description shouldn't have a single
    # word dominate it the way moondream's degenerate outputs do.
    words = description.split()
    if len(words) >= 6 and len(set(words)) / len(words) < 0.4:
        logger.warning("Discarding vision description that looks like a repetition loop: %r", description[:120])
        return None
    return description or None


def generate_social_caption(
    *,
    kind: str,
    language_rule: str,
    page_persona: str | None = None,
    page_tone: str | None = None,
    page_detected_type: str | None = None,
    product_text: str | None = None,
    user_context: str | None = None,
    image_bytes: bytes | None = None,
) -> str:
    """Write a social post caption/hashtags that actually reflects the photo
    being posted (if one is attached) and matches the connected page's own
    persona/tone — instead of guessing blind from a one-line text prompt.
    """
    persona_line = (
        f"This post is for the Facebook/Instagram page '{page_persona}', whose tone of voice is "
        f"'{page_tone or 'friendly and professional'}' and nature is '{page_detected_type or 'general retail'}'. "
        f"Match that persona and tone exactly.\n"
        if page_persona
        else "Match a friendly, professional retail brand voice.\n"
    )
    product_line = (
        f"The product being promoted is '{product_text}' — name it explicitly and describe it precisely; "
        f"do not write a generic caption that omits the product name.\n"
        if product_text
        else ""
    )
    context_line = f"Extra context from the merchant: {user_context}.\n" if user_context else ""

    photo_line = None
    if image_bytes:
        description = _describe_photo(image_bytes)
        if description:
            photo_line = f"What the attached photo actually shows: {description}\n"
        else:
            logger.warning("Vision description unavailable or unusable, writing caption from text details only.")

    if kind == "hashtags":
        task_line = (
            "Suggest 8 viral hashtags for this post (no # symbol, space separated). If the photo description "
            "mentions a specific product or style, reflect that in the hashtags.\n"
            if photo_line
            else "Suggest 8 viral hashtags for this post (no # symbol, space separated).\n"
        )
    else:
        task_line = (
            "Write an engaging, short social media caption describing what's actually in the photo (the item, its "
            "color/style, the vibe) — do not write a generic caption that could apply to any photo.\n"
            if photo_line
            else "Write an engaging short social media caption for this post.\n"
        )

    prompt = (
        f"{language_rule}\n{persona_line}{product_line}{context_line}{photo_line or ''}{task_line}"
        f"Reply with ONLY the {'hashtags' if kind == 'hashtags' else 'caption'} text — no preamble, no quotes. "
        f"{language_rule}"
    )

    return chat_completion("You are a social media copywriter for retail brands.", prompt, max_tokens=220)
