import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.loyalty import LoyaltyReward
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductVariant, StockLedgerEntry
from app.models.team_member import TeamMember, TeamRole
from app.schemas.order import OrderCreate, OrderImportRequest, OrderImportResult, OrderOut, OrderStatusUpdate
from app.services.automation_engine import trigger_event

router = APIRouter(prefix="/orders", tags=["orders"])

# FR-CUST-03: draft a thank-you/reward on these delivered-order milestones.
LOYALTY_MILESTONES = {2, 3, 5, 10}


@router.get("", response_model=list[OrderOut])
def list_orders(
    status_filter: OrderStatus | None = None,
    current_user: TeamMember = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    query = (
        db.query(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .filter(Order.shop_id == current_user.shop_id)
    )
    if status_filter:
        query = query.filter(Order.status == status_filter)
    orders = query.order_by(Order.created_at.desc()).all()
    results = []
    for order in orders:
        out = OrderOut.model_validate(order)
        out.customer_name = order.customer.name if order.customer else None
        results.append(out)
    return results


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> OrderOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.shop_id == current_user.shop_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # FR-FIN-01/overview COGS: snapshot each variant's current cost at order time,
    # so later cost changes don't retroactively change a past order's profit.
    variant_ids = [i.variant_id for i in payload.items if i.variant_id is not None]
    cost_by_variant: dict[uuid.UUID, float] = {}
    if variant_ids:
        rows = (
            db.query(ProductVariant.id, Product.cost)
            .join(Product, ProductVariant.product_id == Product.id)
            .filter(ProductVariant.id.in_(variant_ids))
            .all()
        )
        cost_by_variant = {row[0]: row[1] for row in rows}

    items = [
        OrderItem(
            variant_id=i.variant_id,
            name_snapshot=i.name_snapshot,
            quantity=i.quantity,
            unit_price=i.unit_price,
            unit_cost_snapshot=cost_by_variant.get(i.variant_id),
        )
        for i in payload.items
    ]
    total = sum(i.quantity * i.unit_price for i in items)

    order = Order(
        shop_id=current_user.shop_id,
        customer_id=customer.id,
        source_channel=payload.source_channel,
        status=OrderStatus.NEW,
        total_amount=total,
        items=items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/export.csv")
def export_orders_csv(
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """FR-ORD spreadsheet sync: export orders as CSV."""
    orders = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.shop_id == current_user.shop_id)
        .order_by(Order.created_at.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "order_id",
            "customer_id",
            "status",
            "source_channel",
            "total_amount",
            "created_at",
            "item_name",
            "quantity",
            "unit_price",
        ]
    )
    for order in orders:
        if not order.items:
            writer.writerow(
                [
                    order.id,
                    order.customer_id,
                    order.status.value,
                    order.source_channel or "",
                    order.total_amount,
                    order.created_at.isoformat() if order.created_at else "",
                    "",
                    "",
                    "",
                ]
            )
        else:
            for item in order.items:
                writer.writerow(
                    [
                        order.id,
                        order.customer_id,
                        order.status.value,
                        order.source_channel or "",
                        order.total_amount,
                        order.created_at.isoformat() if order.created_at else "",
                        item.name_snapshot,
                        item.quantity,
                        item.unit_price,
                    ]
                )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


@router.post("/import", response_model=OrderImportResult, status_code=status.HTTP_201_CREATED)
def import_orders(
    payload: OrderImportRequest,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> OrderImportResult:
    """FR-ORD spreadsheet sync: create orders from spreadsheet rows (matched by phone)."""
    created_ids: list[uuid.UUID] = []
    for row in payload.rows:
        customer = None
        if row.customer_phone:
            customer = (
                db.query(Customer)
                .filter(Customer.shop_id == current_user.shop_id, Customer.phone == row.customer_phone)
                .first()
            )
        if customer is None:
            customer = Customer(
                shop_id=current_user.shop_id,
                name=row.customer_name,
                phone=row.customer_phone,
                source="spreadsheet",
            )
            db.add(customer)
            db.flush()

        item = OrderItem(
            name_snapshot=row.item_name,
            quantity=row.quantity,
            unit_price=row.unit_price,
        )
        order = Order(
            shop_id=current_user.shop_id,
            customer_id=customer.id,
            source_channel=row.source_channel or "spreadsheet",
            status=OrderStatus.NEW,
            total_amount=row.quantity * row.unit_price,
            items=[item],
        )
        db.add(order)
        db.flush()
        created_ids.append(order.id)

    db.commit()
    return OrderImportResult(created=len(created_ids), order_ids=created_ids)


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    current_user: TeamMember = Depends(require_role(TeamRole.SALES)),
    db: Session = Depends(get_db),
) -> OrderOut:
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id, Order.shop_id == current_user.shop_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    previous_status = order.status
    order.status = payload.status

    # FR-CAT-05: decrement stock on confirmation, restore on cancellation/return.
    if previous_status != OrderStatus.CONFIRMED and payload.status == OrderStatus.CONFIRMED:
        _apply_stock_delta(db, order, sign=-1, reason="order_confirmed", actor_id=current_user.id)
    elif previous_status == OrderStatus.CONFIRMED and payload.status in (
        OrderStatus.RETURNED,
        OrderStatus.ON_HOLD,
    ):
        _apply_stock_delta(db, order, sign=+1, reason="order_cancelled", actor_id=current_user.id)

    if previous_status != OrderStatus.DELIVERED and payload.status == OrderStatus.DELIVERED:
        _maybe_draft_loyalty_reward(db, order)

    # FR-DOC-04: auto-issue PDFs for active rules matching this status transition
    from app.services.auto_issue import STATUS_TO_TRIGGER, run_auto_issue

    auto_trigger = STATUS_TO_TRIGGER.get(payload.status.value)
    if auto_trigger and previous_status != payload.status:
        run_auto_issue(db, order.shop_id, auto_trigger, order.id)

    db.add(order)
    db.commit()
    db.refresh(order)

    if previous_status != OrderStatus.CONFIRMED and payload.status == OrderStatus.CONFIRMED:
        trigger_event(db, order.shop_id, "order.confirmed", {"order_id": order.id, "actor_id": current_user.id})
        _check_low_stock_and_trigger(db, order, current_user.id)

    if previous_status != payload.status and payload.status in (OrderStatus.CONFIRMED, OrderStatus.DECLINED):
        _notify_customer_of_decision(db, order)
        db.commit()

    return order


def _notify_customer_of_decision(db: Session, order: Order) -> None:
    """Tell the customer, over the same chat conversation their order came
    from, whether the seller confirmed or declined it. Only applicable to
    orders placed via chat — a manually/spreadsheet-created order has no
    conversation to reply into."""
    if order.conversation_id is None:
        return

    from app.models.conversation import Conversation, Message, MessageDirection
    from app.services.channel_outbound import deliver_outbound

    conversation = db.get(Conversation, order.conversation_id)
    if conversation is None:
        return

    ref = order.invoice_number or str(order.id).split("-")[0].upper()
    if order.status == OrderStatus.CONFIRMED:
        text = f"✅ Good news — your order (Invoice {ref}) has been confirmed by the seller and is being prepared."
    else:
        text = f"We're sorry, your order (Invoice {ref}) could not be accepted by the seller and has been declined."

    message = Message(
        conversation_id=conversation.id,
        direction=MessageDirection.OUTBOUND,
        text=text,
        sent_by_ai=True,
    )
    db.add(message)
    deliver_outbound(db, conversation, text, message=message)


def _apply_stock_delta(db: Session, order: Order, sign: int, reason: str, actor_id: uuid.UUID) -> None:
    for item in order.items:
        if item.variant_id is None:
            continue
        variant = db.get(ProductVariant, item.variant_id)
        if variant is None:
            continue
        variant.stock_qty += sign * item.quantity
        db.add(variant)
        db.add(
            StockLedgerEntry(
                variant_id=variant.id,
                delta_qty=sign * item.quantity,
                reason=reason,
                order_id=order.id,
                created_by=actor_id,
            )
        )


def _maybe_draft_loyalty_reward(db: Session, order: Order) -> None:
    delivered_count = (
        db.query(Order)
        .filter(Order.customer_id == order.customer_id, Order.status == OrderStatus.DELIVERED)
        .count()
        + 1  # this order is about to become DELIVERED
    )
    if delivered_count not in LOYALTY_MILESTONES:
        return

    db.add(
        LoyaltyReward(
            shop_id=order.shop_id,
            customer_id=order.customer_id,
            milestone_order_number=delivered_count,
            draft_message=(
                f"Thank you for being a loyal customer — this is your {delivered_count}th order with us! "
                "We'd love to offer you something special as a thank-you."
            ),
        )
    )


def _check_low_stock_and_trigger(db: Session, order: Order, actor_id: uuid.UUID) -> None:
    """Fires the 'stock.low' event (e.g. for a pre-built low-stock-alert recipe)
    for any variant in this order that just crossed its reorder point."""
    for item in order.items:
        if item.variant_id is None:
            continue
        variant = db.get(ProductVariant, item.variant_id)
        if variant is not None and variant.stock_qty <= variant.reorder_point:
            trigger_event(
                db,
                order.shop_id,
                "stock.low",
                {"related_id": variant.id, "actor_id": actor_id},
            )
