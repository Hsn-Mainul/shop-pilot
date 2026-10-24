import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.finance import LedgerAccountType, LedgerEntry
from app.models.order import Order
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.team_member import TeamMember, TeamRole
from app.schemas.payment import PaymentCreate, PaymentOut

router = APIRouter(prefix="/payments", tags=["payments"])

_METHOD_TO_LEDGER_ACCOUNT = {
    PaymentMethod.CASH: LedgerAccountType.CASH,
    PaymentMethod.COD: LedgerAccountType.CASH,
    PaymentMethod.BKASH: LedgerAccountType.WALLET,
    PaymentMethod.NAGAD: LedgerAccountType.WALLET,
    PaymentMethod.BANK: LedgerAccountType.BANK,
    PaymentMethod.CARD: LedgerAccountType.BANK,
}


@router.get("", response_model=list[PaymentOut])
def list_payments(
    status_filter: PaymentStatus | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PaymentOut]:
    query = db.query(Payment).join(Order).filter(Order.shop_id == current_user.shop_id)
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    return query.order_by(Payment.created_at.asc()).all()


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def record_payment(
    payload: PaymentCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> PaymentOut:
    order = (
        db.query(Order)
        .filter(Order.id == payload.order_id, Order.shop_id == current_user.shop_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    payment = Payment(status=PaymentStatus.PENDING, **payload.model_dump())

    # Simple auto-match heuristic (FR-PAY-02): amount matches order total exactly
    # and a transaction reference was supplied -> flag ready to confirm;
    # otherwise it needs a human to review the match.
    if payment.amount == order.total_amount and payment.trx_ref:
        payment.status = PaymentStatus.PENDING
    else:
        payment.status = PaymentStatus.NEEDS_REVIEW

    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/{payment_id}/confirm", response_model=PaymentOut)
def confirm_payment(
    payment_id: uuid.UUID,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> PaymentOut:
    payment = (
        db.query(Payment)
        .join(Order)
        .filter(Payment.id == payment_id, Order.shop_id == current_user.shop_id)
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    payment.status = PaymentStatus.CONFIRMED
    db.add(payment)

    # FR-FIN-01: post this confirmation to the books automatically.
    db.add(
        LedgerEntry(
            shop_id=current_user.shop_id,
            account_type=_METHOD_TO_LEDGER_ACCOUNT[payment.method],
            amount=payment.amount,
            ref_type="payment",
            ref_id=payment.id,
        )
    )

    # FR-DOC-04: money receipt (and other) auto-issue rules
    from app.services.auto_issue import run_auto_issue

    run_auto_issue(db, current_user.shop_id, "payment_recorded", payment.order_id)

    db.commit()
    db.refresh(payment)
    return payment
