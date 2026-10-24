"""Tests for Ollama client, vector embeddings, and RAG search."""
import pytest
from app.integrations.ollama import check_ollama_status, cosine_similarity, get_embedding
from app.services.rag_service import prepare_knowledge_text, prepare_product_text


def test_cosine_similarity_basic():
    # Identical vectors should have similarity 1.0
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0, 3.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 1.0

    # Orthogonal vectors should have similarity 0.0
    v3 = [1.0, 0.0]
    v4 = [0.0, 1.0]
    assert pytest.approx(cosine_similarity(v3, v4), 0.001) == 0.0


def test_ollama_status_check():
    status = check_ollama_status()
    assert isinstance(status, dict)
    assert "online" in status
    assert "models" in status
    assert "chat_model" in status
    assert "embed_model" in status


def test_ollama_embedding_generation():
    status = check_ollama_status()
    if not status.get("online") or not status.get("embed_ready"):
        pytest.skip("Local Ollama or embed model not active")

    emb = get_embedding("ShopPilot delivery policy in Dhaka")
    assert emb is not None
    assert len(emb) == 384
    assert isinstance(emb[0], float)
