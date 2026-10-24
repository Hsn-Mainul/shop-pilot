import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.product import Product, ProductVariant, StockLedgerEntry
from app.models.team_member import TeamMember, TeamRole
from app.schemas.product import (
    BulkProductImportRequest,
    BulkProductImportResult,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustRequest,
    StockLedgerOut,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    q: str | None = None,
    kind: str | None = Query(None, description="product | service"),
    page_id: str | None = Query(None, description="Filter to a specific connected page's own catalog"),
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProductOut]:
    query = (
        db.query(Product)
        .options(selectinload(Product.variants))
        .filter(Product.shop_id == current_user.shop_id)
    )
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if kind:
        query = query.filter(Product.kind == kind)
    if page_id:
        query = query.filter((Product.page_id == page_id) | (Product.page_id.is_(None)))
    return query.order_by(Product.created_at.desc()).all()


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> ProductOut:
    data = payload.model_dump(exclude={"variants"})
    product = Product(shop_id=current_user.shop_id, **data)
    product.variants = [
        ProductVariant(
            sku=v.sku,
            attributes=v.attributes,
            stock_qty=v.stock_qty,
            reorder_point=v.reorder_point,
            batch_code=v.batch_code,
            serial_numbers=v.serial_numbers or [],
            location=v.location,
        )
        for v in payload.variants
    ]
    db.add(product)
    db.commit()
    db.refresh(product)
    try:
        from app.services.rag_service import index_product
        index_product(db, product)
        db.refresh(product)
    except Exception:
        pass
    return product


@router.post("/import", response_model=BulkProductImportResult, status_code=status.HTTP_201_CREATED)
def bulk_import_products(
    payload: BulkProductImportRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> BulkProductImportResult:
    """FR-CAT bulk import — create many products (+ one default variant) in one request."""
    created_ids: list[uuid.UUID] = []
    for item in payload.items:
        product = Product(
            shop_id=current_user.shop_id,
            name=item.name,
            price=item.price,
            category=item.category,
            cost=item.cost,
            kind=item.kind,
            pricing_mode=item.pricing_mode,
        )
        product.variants = [
            ProductVariant(
                sku=item.sku,
                attributes={"source": "bulk_import"},
                stock_qty=item.stock_qty,
                reorder_point=2,
            )
        ]
        db.add(product)
        db.flush()
        created_ids.append(product.id)
    db.commit()
    return BulkProductImportResult(created=len(created_ids), product_ids=created_ids)


@router.get("/stock-ledger", response_model=list[StockLedgerOut])
def list_stock_ledger(
    variant_id: uuid.UUID | None = None,
    limit: int = Query(100, le=500),
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StockLedgerOut]:
    """FR-CAT-05: auditable stock history for this shop's variants."""
    query = (
        db.query(StockLedgerEntry)
        .join(ProductVariant, StockLedgerEntry.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .filter(Product.shop_id == current_user.shop_id)
    )
    if variant_id:
        query = query.filter(StockLedgerEntry.variant_id == variant_id)
    rows = query.order_by(StockLedgerEntry.created_at.desc()).limit(limit).all()
    return [
        StockLedgerOut(
            id=r.id,
            variant_id=r.variant_id,
            delta_qty=r.delta_qty,
            reason=r.reason,
            order_id=r.order_id,
            created_by=r.created_by,
            note=getattr(r, "note", None),
            created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        )
        for r in rows
    ]


@router.post("/stock-adjust", response_model=StockLedgerOut, status_code=status.HTTP_201_CREATED)
def adjust_stock(
    payload: StockAdjustRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.WAREHOUSE)),
    db: Session = Depends(get_db),
) -> StockLedgerOut:
    """Manual receive / count / adjust with ledger row (FR-CAT-05)."""
    variant = (
        db.query(ProductVariant)
        .join(Product)
        .filter(ProductVariant.id == payload.variant_id, Product.shop_id == current_user.shop_id)
        .first()
    )
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    variant.stock_qty = (variant.stock_qty or 0) + payload.delta_qty
    if payload.batch_code is not None:
        variant.batch_code = payload.batch_code
    if payload.serial_numbers is not None:
        existing = list(variant.serial_numbers or [])
        for s in payload.serial_numbers:
            if s not in existing:
                existing.append(s)
        variant.serial_numbers = existing

    entry = StockLedgerEntry(
        variant_id=variant.id,
        delta_qty=payload.delta_qty,
        reason=payload.reason,
        created_by=current_user.id,
        note=payload.note,
    )
    db.add(variant)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return StockLedgerOut(
        id=entry.id,
        variant_id=entry.variant_id,
        delta_qty=entry.delta_qty,
        reason=entry.reason,
        order_id=entry.order_id,
        created_by=entry.created_by,
        note=entry.note,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
    )


def _get_owned_product(product_id: uuid.UUID, current_user: TeamMember, db: Session) -> Product:
    product = (
        db.query(Product)
        .options(selectinload(Product.variants))
        .filter(Product.id == product_id, Product.shop_id == current_user.shop_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = _get_owned_product(product_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.add(product)
    db.commit()
    db.refresh(product)
    try:
        from app.services.rag_service import index_product
        index_product(db, product)
        db.refresh(product)
    except Exception:
        pass
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    product = _get_owned_product(product_id, current_user, db)
    db.delete(product)
    db.commit()
