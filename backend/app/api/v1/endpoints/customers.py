import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.review import Review
from app.models.team_member import TeamMember, TeamRole
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate
from app.schemas.review import ReviewCreate, ReviewOut

router = APIRouter(prefix="/customers", tags=["customers"])

# FR-CUST-02 segmentation thresholds: tune later from real data.
VIP_ORDER_COUNT = 5
REPEAT_ORDER_COUNT = 2


@router.get("", response_model=list[CustomerOut])
def list_customers(
    q: str | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    query = db.query(Customer).filter(Customer.shop_id == current_user.shop_id)
    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%") | Customer.phone.ilike(f"%{q}%"))
    return query.order_by(Customer.created_at.desc()).all()


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = Customer(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _get_owned_customer(customer_id: uuid.UUID, current_user: TeamMember, db: Session) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.shop_id == current_user.shop_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = _get_owned_customer(customer_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/segments/recompute", response_model=list[CustomerOut])
def recompute_segments(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[CustomerOut]:
    """Score every customer with a delivered order into a segment (FR-CUST-02)."""
    delivered_counts = Counter(
        row.customer_id
        for row in db.query(Order.customer_id)
        .filter(Order.shop_id == current_user.shop_id, Order.status == OrderStatus.DELIVERED)
        .all()
    )
    customers = db.query(Customer).filter(Customer.shop_id == current_user.shop_id).all()
    for customer in customers:
        count = delivered_counts.get(customer.id, 0)
        if count >= VIP_ORDER_COUNT:
            customer.segment = "vip"
        elif count >= REPEAT_ORDER_COUNT:
            customer.segment = "repeat_customer"
        elif count == 1:
            customer.segment = "one_time_customer"
        else:
            customer.segment = "no_orders_yet"
        db.add(customer)
    db.commit()
    return customers


@router.patch("/{customer_id}/block", response_model=CustomerOut)
def toggle_block_customer(
    customer_id: uuid.UUID,
    blocked: bool = True,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> CustomerOut:
    customer = _get_owned_customer(customer_id, current_user, db)
    customer.is_blocked = blocked
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


reviews_router = APIRouter(prefix="/reviews", tags=["customers"])


@reviews_router.get("", response_model=list[ReviewOut])
def list_reviews(
    include_hidden: bool = False,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReviewOut]:
    query = db.query(Review).join(Customer).filter(Customer.shop_id == current_user.shop_id)
    if not include_hidden:
        query = query.filter(Review.is_hidden.is_(False))
    return query.order_by(Review.created_at.desc()).all()


@reviews_router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    customer = _get_owned_customer(payload.customer_id, current_user, db)
    review = Review(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@reviews_router.patch("/{review_id}/hide", response_model=ReviewOut)
def hide_review(
    review_id: uuid.UUID,
    hidden: bool = True,
    current_user: TeamMember = Depends(require_role(TeamRole.SUPPORT)),
    db: Session = Depends(get_db),
) -> ReviewOut:
    review = (
        db.query(Review)
        .filter(Review.id == review_id, Review.shop_id == current_user.shop_id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    review.is_hidden = hidden
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
