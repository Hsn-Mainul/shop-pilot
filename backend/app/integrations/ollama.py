"""Ollama native client for local LLM inference and vector embeddings (RAG).

Supports:
- Server health & model inventory check (GET /api/tags, GET /api/version)
- Fast dense vector embeddings via Ollama (POST /api/embed)
- Batch embedding generation for shop knowledge items & products
- Cosine similarity computation for local semantic vector search
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try numpy for accelerated vector arithmetic; fall back to pure math if needed
try:
    import numpy as np

    def _cosine_similarity_np(v1: list[float], v2: list[float]) -> float:
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    cosine_similarity = _cosine_similarity_np
except ImportError:
    import math

    def _cosine_similarity_py(v1: list[float], v2: list[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    cosine_similarity = _cosine_similarity_py


def get_ollama_base_url() -> str:
    """Return the raw Ollama base URL (e.g. 'http://localhost:11434')."""
    base = settings.ollama_base_url or "http://localhost:11434"
    return base.rstrip("/")


def check_ollama_status() -> dict[str, Any]:
    """Inspect local Ollama daemon connectivity, installed models, and embed capability."""
    base_url = get_ollama_base_url()
    result: dict[str, Any] = {
        "online": False,
        "base_url": base_url,
        "version": None,
        "models": [],
        "chat_model": settings.ollama_chat_model,
        "chat_ready": False,
        "embed_model": settings.ollama_embed_model,
        "embed_ready": False,
        "error": None,
    }

    try:
        with httpx.Client(timeout=4.0) as client:
            v_res = client.get(f"{base_url}/api/version")
            if v_res.status_code == 200:
                result["version"] = v_res.json().get("version")
                result["online"] = True

            tags_res = client.get(f"{base_url}/api/tags")
            if tags_res.status_code == 200:
                models_info = tags_res.json().get("models", [])
                model_names = [m.get("name", "") for m in models_info if m.get("name")]
                result["models"] = model_names
                result["online"] = True

                chat_target = settings.ollama_chat_model.lower()
                result["chat_ready"] = any(
                    m.lower() == chat_target or m.lower().startswith(f"{chat_target}:")
                    for m in model_names
                )

                embed_target = settings.ollama_embed_model.lower()
                result["embed_ready"] = any(
                    m.lower() == embed_target or m.lower().startswith(f"{embed_target}:")
                    for m in model_names
                )
    except Exception as exc:
        result["error"] = str(exc)
        result["online"] = False

    return result


def get_embedding(text: str, model: str | None = None) -> list[float] | None:
    """Generate a single dense embedding vector for the given text.

    Uses Ollama's POST /api/embed API.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return None

    base_url = get_ollama_base_url()
    model_name = model or settings.ollama_embed_model

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                f"{base_url}/api/embed",
                json={"model": model_name, "input": clean_text},
            )
            if res.status_code == 200:
                data = res.json()
                embeddings = data.get("embeddings") or []
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]

            # Fallback to legacy /api/embeddings endpoint
            res_legacy = client.post(
                f"{base_url}/api/embeddings",
                json={"model": model_name, "prompt": clean_text},
            )
            if res_legacy.status_code == 200:
                return res_legacy.json().get("embedding")
    except Exception as exc:
        logger.warning(f"Ollama get_embedding failed for model {model_name}: {exc}")

    return None


def get_batch_embeddings(
    texts: list[str],
    model: str | None = None,
    batch_size: int = 32,
) -> list[list[float] | None]:
    """Generate dense embeddings for a batch of strings, chunked to avoid memory spikes."""
    if not texts:
        return []

    base_url = get_ollama_base_url()
    model_name = model or settings.ollama_embed_model
    results: list[list[float] | None] = []

    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        # Clean chunk texts
        cleaned = [t.strip() if t and t.strip() else " " for t in chunk]
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(
                    f"{base_url}/api/embed",
                    json={"model": model_name, "input": cleaned},
                )
                if res.status_code == 200:
                    chunk_embeddings = res.json().get("embeddings") or []
                    for idx, emb in enumerate(chunk_embeddings):
                        results.append(emb if chunk[idx].strip() else None)
                    continue
        except Exception as exc:
            logger.warning(f"Ollama batch embedding chunk failed: {exc}")

        # Fallback element by element if batch call failed
        for t in chunk:
            results.append(get_embedding(t, model=model_name))

    return results


def extract_slip_data(image_bytes: bytes, filename: str = "") -> dict[str, Any]:
    """Use Qwen2.5-VL in Ollama to extract transaction details from payment slip screenshots.

    Supports bKash, Nagad, Rocket, Upay, Bank deposit slips, and card receipts.
    """
    import base64
    import json
    import re

    base_url = get_ollama_base_url()
    model_name = settings.ollama_chat_model  # qwen2.5vl:3b

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "You are an expert OCR and financial document analysis assistant specialized in Bangladesh "
        "mobile financial services (bKash, Nagad, Rocket, Upay) and bank deposit slips.\n"
        "Examine the attached payment screenshot or slip image and extract the transaction details.\n"
        "Return ONLY a valid JSON object with the following keys:\n"
        "{\n"
        '  "is_payment_slip": true,\n'
        '  "method": "bkash" or "nagad" or "bank" or "card" or "other",\n'
        '  "amount": numeric float or null,\n'
        '  "trx_id": string transaction ID or null,\n'
        '  "sender_number": string phone or account number or null,\n'
        '  "recipient": string merchant name or recipient number or null,\n'
        '  "date_time": string timestamp or null,\n'
        '  "confidence": float between 0.0 and 1.0\n'
        "}\n"
        "If the image is not a payment slip or receipt, set is_payment_slip to false."
    )

    result: dict[str, Any] = {
        "is_payment_slip": False,
        "method": "bkash",
        "amount": None,
        "trx_id": None,
        "sender_number": None,
        "recipient": None,
        "date_time": None,
        "confidence": 0.0,
        "raw_text": "",
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            res = client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [b64_image],
                        }
                    ],
                    "stream": False,
                },
            )

            if res.status_code == 200:
                raw_content = res.json().get("message", {}).get("content", "")
                result["raw_text"] = raw_content

                # Parse JSON block
                json_str = raw_content
                if "```json" in raw_content:
                    json_str = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    json_str = raw_content.split("```")[1].split("```")[0].strip()

                parsed = json.loads(json_str)

                # Normalize method
                raw_method = str(parsed.get("method", "")).lower()
                if "bkash" in raw_method:
                    method = "bkash"
                elif "nagad" in raw_method:
                    method = "nagad"
                elif "bank" in raw_method:
                    method = "bank"
                elif "card" in raw_method:
                    method = "card"
                else:
                    method = raw_method or "bkash"

                # Parse amount
                raw_amt = parsed.get("amount")
                amount = None
                if raw_amt is not None:
                    try:
                        if isinstance(raw_amt, str):
                            # Clean "Tk 1,850.00" -> 1850.0
                            cleaned_num = re.sub(r"[^\d.]", "", raw_amt)
                            amount = float(cleaned_num) if cleaned_num else None
                        else:
                            amount = float(raw_amt)
                    except (ValueError, TypeError):
                        amount = None

                result["is_payment_slip"] = bool(parsed.get("is_payment_slip", True))
                result["method"] = method
                result["amount"] = amount
                result["trx_id"] = parsed.get("trx_id")
                result["sender_number"] = parsed.get("sender_number")
                result["recipient"] = parsed.get("recipient")
                result["date_time"] = parsed.get("date_time")
                result["confidence"] = float(parsed.get("confidence") or 0.95)

    except Exception as exc:
        logger.warning(f"Ollama vision extract_slip_data failed: {exc}")
        result["error"] = str(exc)

    return result


def _downscale_for_vision(image_bytes: bytes, max_dimension: int = 768) -> bytes:
    """Shrink a photo before sending it to the local vision model.

    On CPU-only inference, a full-resolution upload (e.g. 1920x1128) can take
    several minutes or time out entirely — visual token count scales with
    resolution. Capping the longest side keeps inference fast without
    meaningfully hurting the model's ability to describe the subject.
    """
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(image_bytes))
        img.thumbnail((max_dimension, max_dimension))
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as exc:
        logger.warning(f"Image downscale for vision failed, using original: {exc}")
        return image_bytes


def generate_vision_text(
    prompt: str, image_bytes: bytes, max_tokens: int = 300, timeout_seconds: float = 20.0
) -> str | None:
    """Ask a local vision model to look at an image and respond in free text
    to `prompt` — used for image-aware social captions, where the caption
    should actually reflect what's in the photo rather than being generated
    blind from text alone.

    Qwen2.5-VL's vision encoder is slow on CPU-only inference — in testing, the
    image-processing step alone took ~150-180s regardless of how small the
    photo was downscaled to (a plain text call to the same model took ~5s), so
    the bottleneck is the vision tower itself, not image size. We use
    `moondream` here instead, which does the same job in ~5-10s on this
    hardware. Returns None on timeout or if Ollama is unreachable.
    """
    import base64

    base_url = get_ollama_base_url()
    model_name = "moondream"
    b64_image = base64.b64encode(_downscale_for_vision(image_bytes)).decode("utf-8")

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            res = client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [b64_image],
                        }
                    ],
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {"num_predict": max_tokens},
                },
            )
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content", "")
                return content.strip() or None
            logger.warning(f"Ollama vision chat returned {res.status_code}: {res.text[:200]}")
    except Exception as exc:
        logger.warning(f"Ollama vision generate_vision_text failed: {exc}")

    return None
