"""RAG (Retrieval-Augmented Generation) & Local Vector Search Service.

Uses Ollama embedding models (e.g. all-minilm) to generate dense vector
embeddings for:
1. Shop AI Knowledge Items (facts, policies, instructions, FAQs)
2. Live Product Catalog (names, categories, descriptions, variant stocks/prices)

When customers or merchants interact with the AI assistant, this service
retrieves the most semantically relevant facts and products to create a
compact, accurate, grounded prompt context — eliminating prompt overflow,
reducing latency, and stopping hallucinations.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.ollama import (
    cosine_similarity,
    get_batch_embeddings,
    get_embedding,
)
from app.models.ai_knowledge import AIKnowledgeItem
from app.models.product import Product

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {
    "BDT": "৳",
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
    "PKR": "₨",
    "NPR": "₨",
    "AED": "AED",
    "SAR": "SAR",
    "MYR": "RM",
}


def format_money(amount: Any, currency: str) -> str:
    """Render a price with an unambiguous currency symbol + code, e.g. '৳499.00 (BDT)'."""
    symbol = CURRENCY_SYMBOLS.get((currency or "BDT").upper(), "")
    return f"{symbol}{amount} ({currency})" if symbol else f"{amount} {currency}"


def prepare_knowledge_text(item: AIKnowledgeItem) -> str:
    """Serialize a knowledge item into a dense search string."""
    cat_label = item.category.value if hasattr(item.category, "value") else str(item.category)
    return f"Knowledge [{cat_label}]: {item.title}\n{item.content}".strip()


def prepare_product_text(prod: Product, currency: str | None = None) -> str:
    """Serialize a product with its variants and stock levels into a search string."""
    variant_details = []
    total_stock = 0
    for v in prod.variants or []:
        stock = v.stock_qty or 0
        total_stock += stock
        attrs = ", ".join(f"{k}: {val}" for k, val in (v.attributes or {}).items())
        status = f"{stock} in stock" if stock > 0 else "Out of stock"
        if attrs:
            variant_details.append(f"{attrs} ({status})")
        else:
            variant_details.append(status)

    variants_str = f" | Variants: {'; '.join(variant_details)}" if variant_details else ""
    category_str = f" | Category: {prod.category}" if prod.category else ""
    desc_str = f" | Details: {prod.description}" if prod.description else ""
    currency_code = currency or getattr(getattr(prod, "shop", None), "currency", None) or "BDT"
    price_str = format_money(prod.price, currency_code)

    return (
        f"Product: {prod.name}{category_str} | Price: {price_str}{desc_str}{variants_str}"
    ).strip()


def index_knowledge_item(db: Session, item: AIKnowledgeItem) -> bool:
    """Generate and store embedding for a single knowledge item."""
    text = prepare_knowledge_text(item)
    emb = get_embedding(text)
    if emb:
        item.embedding = emb
        db.add(item)
        db.commit()
        return True
    return False


def index_product(db: Session, product: Product) -> bool:
    """Generate and store embedding for a single product."""
    text = prepare_product_text(product)
    emb = get_embedding(text)
    if emb:
        product.embedding = emb
        db.add(product)
        db.commit()
        return True
    return False


def reindex_shop_knowledge_and_catalog(
    db: Session, shop_id: uuid.UUID
) -> dict[str, Any]:
    """Reindex all approved knowledge items and products for a shop using batch embeddings."""
    # 1. Knowledge items
    knowledge_items = (
        db.query(AIKnowledgeItem)
        .filter(
            AIKnowledgeItem.shop_id == shop_id,
            AIKnowledgeItem.is_pending_approval.is_(False),
        )
        .all()
    )
    k_texts = [prepare_knowledge_text(k) for k in knowledge_items]
    k_embeddings = get_batch_embeddings(k_texts) if k_texts else []

    k_count = 0
    for item, emb in zip(knowledge_items, k_embeddings):
        if emb:
            item.embedding = emb
            db.add(item)
            k_count += 1

    # 2. Products
    from app.models.shop import Shop

    shop_currency = db.query(Shop.currency).filter(Shop.id == shop_id).scalar() or "BDT"
    products = db.query(Product).filter(Product.shop_id == shop_id).all()
    p_texts = [prepare_product_text(p, shop_currency) for p in products]
    p_embeddings = get_batch_embeddings(p_texts) if p_texts else []

    p_count = 0
    for prod, emb in zip(products, p_embeddings):
        if emb:
            prod.embedding = emb
            db.add(prod)
            p_count += 1

    db.commit()

    return {
        "shop_id": str(shop_id),
        "indexed_knowledge_count": k_count,
        "total_knowledge_count": len(knowledge_items),
        "indexed_products_count": p_count,
        "total_products_count": len(products),
    }


def search_knowledge_and_catalog(
    db: Session,
    shop_id: uuid.UUID,
    query: str,
    top_k_knowledge: int = 5,
    top_k_products: int = 5,
    min_similarity: float = 0.20,
    page_id: str | None = None,
    include_products: bool = True,
    currency: str | None = None,
) -> dict[str, Any]:
    """Perform hybrid semantic vector search over shop knowledge and products.

    Falls back smoothly to lexical/keyword matching if vector embeddings are
    unavailable or Ollama is offline.
    """
    clean_query = query.strip()
    if not clean_query:
        return {"knowledge": [], "products": [], "mode": "empty"}

    query_vec = get_embedding(clean_query)

    # 1. Search knowledge items
    query_builder = db.query(AIKnowledgeItem).filter(
        AIKnowledgeItem.shop_id == shop_id,
        AIKnowledgeItem.is_pending_approval.is_(False),
    )
    if page_id:
        query_builder = query_builder.filter(
            (AIKnowledgeItem.page_id == page_id) | (AIKnowledgeItem.page_id.is_(None))
        )
    knowledge_items = query_builder.all()

    scored_knowledge: list[dict[str, Any]] = []
    if query_vec:
        for k in knowledge_items:
            sim = 0.0
            if k.embedding:
                sim = cosine_similarity(query_vec, k.embedding)
            else:
                # Lexical fallback if item has no vector yet
                if clean_query.lower() in k.title.lower() or clean_query.lower() in k.content.lower():
                    sim = 0.45
            if sim >= min_similarity:
                scored_knowledge.append({
                    "id": k.id,
                    "title": k.title,
                    "content": k.content,
                    "category": k.category.value if hasattr(k.category, "value") else str(k.category),
                    "similarity": round(float(sim), 4),
                })
        scored_knowledge.sort(key=lambda x: x["similarity"], reverse=True)
        scored_knowledge = scored_knowledge[:top_k_knowledge]
    else:
        # Keyword matching fallback
        q_lower = clean_query.lower()
        for k in knowledge_items:
            if q_lower in k.title.lower() or q_lower in k.content.lower():
                scored_knowledge.append({
                    "id": k.id,
                    "title": k.title,
                    "content": k.content,
                    "category": k.category.value if hasattr(k.category, "value") else str(k.category),
                    "similarity": 0.5,
                })
        scored_knowledge = scored_knowledge[:top_k_knowledge]

    # 2. Search products (only when include_products is True)
    scored_products: list[dict[str, Any]] = []
    if include_products:
        product_query = db.query(Product).filter(Product.shop_id == shop_id)
        if page_id:
            # Only this page's own items, plus any shared (unassigned) products —
            # never another page's catalog, so a multi-page shop's AI stays specific.
            product_query = product_query.filter(
                (Product.page_id == page_id) | (Product.page_id.is_(None))
            )
        products = product_query.all()
        if query_vec:
            for p in products:
                sim = 0.0
                if p.embedding:
                    sim = cosine_similarity(query_vec, p.embedding)
                else:
                    # Lexical fallback
                    p_text = f"{p.name} {p.category or ''} {p.description or ''}".lower()
                    if any(w in p_text for w in clean_query.lower().split()):
                        sim = 0.40
                if sim >= min_similarity:
                    scored_products.append({
                        "id": p.id,
                        "name": p.name,
                        "category": p.category,
                        "price": float(p.price),
                        "description": p.description,
                        "similarity": round(float(sim), 4),
                        "text_summary": prepare_product_text(p, currency),
                    })
            scored_products.sort(key=lambda x: x["similarity"], reverse=True)
            scored_products = scored_products[:top_k_products]
        else:
            q_words = [w for w in clean_query.lower().split() if len(w) > 2]
            for p in products:
                p_text = f"{p.name} {p.category or ''} {p.description or ''}".lower()
                if any(w in p_text for w in q_words) or clean_query.lower() in p.name.lower():
                    scored_products.append({
                        "id": p.id,
                        "name": p.name,
                        "category": p.category,
                        "price": float(p.price),
                        "description": p.description,
                        "similarity": 0.5,
                        "text_summary": prepare_product_text(p, currency),
                    })
            scored_products = scored_products[:top_k_products]

    return {
        "knowledge": scored_knowledge,
        "products": scored_products,
        "mode": "vector" if query_vec else "lexical_fallback",
    }


def get_grounded_rag_context(
    db: Session,
    shop: Any,
    query: str,
    page_id: str | None = None,
    include_products: bool = True,
) -> tuple[list[str], list[uuid.UUID], list[uuid.UUID]]:
    """Build compact, grounded prompt snippets using semantic vector search.

    Returns:
    - snippets: List of text statements to feed into build_shop_system_prompt or build_page_system_prompt
    - used_knowledge_ids: List of AIKnowledgeItem UUIDs retrieved
    - used_product_ids: List of Product UUIDs retrieved
    """
    snippets: list[str] = []
    used_k_ids: list[uuid.UUID] = []
    used_p_ids: list[uuid.UUID] = []

    search_res = search_knowledge_and_catalog(
        db,
        shop.id,
        query,
        top_k_knowledge=5,
        top_k_products=5 if include_products else 0,
        page_id=page_id,
        include_products=include_products,
        currency=getattr(shop, "currency", None),
    )

    for k in search_res.get("knowledge", []):
        snippets.append(f"{k['title']}: {k['content']}")
        used_k_ids.append(k["id"])

    for p in search_res.get("products", []):
        snippets.append(p["text_summary"])
        used_p_ids.append(p["id"])

    # If the search returned very few items (e.g. general greeting or query), include top core policies
    if len(snippets) < 3:
        core_query = (
            db.query(AIKnowledgeItem)
            .filter(
                AIKnowledgeItem.shop_id == shop.id,
                AIKnowledgeItem.is_pending_approval.is_(False),
            )
        )
        if page_id:
            core_query = core_query.filter(
                (AIKnowledgeItem.page_id == page_id) | (AIKnowledgeItem.page_id.is_(None))
            )
        core_items = core_query.limit(3).all()
        for k in core_items:
            s = f"{k.title}: {k.content}"
            if s not in snippets:
                snippets.append(s)
                used_k_ids.append(k.id)

    # Core shop operational policies always grounded ONLY if retail / include_products is True
    if include_products:
        if getattr(shop, "delivery_charge_inside_city", None) is not None:
            snippets.append(
                f"Delivery Charge (Inside City): {shop.delivery_charge_inside_city} {shop.currency}"
            )
        if getattr(shop, "delivery_charge_outside_city", None) is not None:
            snippets.append(
                f"Delivery Charge (Outside City): {shop.delivery_charge_outside_city} {shop.currency}"
            )
        if getattr(shop, "address", None):
            snippets.append(f"Store Address: {shop.address}")
        if getattr(shop, "opening_hours", None):
            snippets.append(f"Operating Hours: {shop.opening_hours}")

    return snippets, used_k_ids, used_p_ids
