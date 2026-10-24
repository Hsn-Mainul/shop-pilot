import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.integrations.couriers import book_parcel
from app.models.customer import Customer
from app.models.delivery import DeliveryParcel, ParcelStatus
from app.models.integration import Integration, IntegrationStatus
from app.models.order import Order
from app.models.team_member import TeamMember, TeamRole
from app.schemas.delivery import ParcelBookRequest, ParcelOut, ParcelStatusUpdate

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/parcels", response_model=list[ParcelOut])
def list_parcels(
    status_filter: ParcelStatus | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ParcelOut]:
    query = db.query(DeliveryParcel).join(Order).filter(Order.shop_id == current_user.shop_id)
    if status_filter:
        query = query.filter(DeliveryParcel.status == status_filter)
    return query.order_by(DeliveryParcel.created_at.desc()).all()


@router.post("/parcels/book", response_model=list[ParcelOut], status_code=status.HTTP_201_CREATED)
def book_parcels(
    payload: ParcelBookRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.WAREHOUSE)),
    db: Session = Depends(get_db),
) -> list[ParcelOut]:
    orders = (
        db.query(Order)
        .filter(Order.id.in_(payload.order_ids), Order.shop_id == current_user.shop_id)
        .all()
    )
    if not orders:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching orders found")

    courier_key = (payload.courier or "local").lower()
    integration = (
        db.query(Integration)
        .filter(
            Integration.shop_id == current_user.shop_id,
            Integration.provider == courier_key,
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .first()
    )
    courier_config = (integration.config if integration else {}) or {}

    parcels: list[DeliveryParcel] = []
    for order in orders:
        customer = db.get(Customer, order.customer_id) if order.customer_id else None
        cod = order.total_amount if order.source_channel != "prepaid" else Decimal("0")
        booking = book_parcel(
            courier_key,
            config=courier_config,
            order_id=order.id,
            cod_amount=cod,
            recipient_name=customer.name if customer else None,
            recipient_phone=customer.phone if customer else None,
            address=getattr(order, "shipping_address", None),
        )
        parcels.append(
            DeliveryParcel(
                order_id=order.id,
                courier=payload.courier,
                status=ParcelStatus.TO_BOOK,
                cod_amount=cod,
                tracking_id=booking.get("tracking_id"),
            )
        )
    db.add_all(parcels)
    db.commit()
    for parcel in parcels:
        db.refresh(parcel)
    return parcels


@router.patch("/parcels/{parcel_id}/status", response_model=ParcelOut)
def update_parcel_status(
    parcel_id: uuid.UUID,
    payload: ParcelStatusUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.WAREHOUSE)),
    db: Session = Depends(get_db),
) -> ParcelOut:
    parcel = (
        db.query(DeliveryParcel)
        .join(Order)
        .filter(DeliveryParcel.id == parcel_id, Order.shop_id == current_user.shop_id)
        .first()
    )
    if parcel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    parcel.status = payload.status
    if payload.status == ParcelStatus.DELIVERED and parcel.cod_amount > 0:
        parcel.cod_remitted = False  # cash is owed by the courier until reconciled separately
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return parcel


@router.get("/cod-summary")
def cod_summary(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    parcels = (
        db.query(DeliveryParcel)
        .join(Order)
        .filter(
            Order.shop_id == current_user.shop_id,
            DeliveryParcel.status == ParcelStatus.DELIVERED,
            DeliveryParcel.cod_remitted.is_(False),
        )
        .all()
    )
    total_outstanding = sum((p.cod_amount for p in parcels), Decimal("0"))
    by_courier: dict[str, Decimal] = {}
    for p in parcels:
        by_courier[p.courier] = by_courier.get(p.courier, Decimal("0")) + p.cod_amount
    return {"total_outstanding": total_outstanding, "by_courier": by_courier}
