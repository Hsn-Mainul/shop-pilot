import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.delivery import DeliveryParcel, ParcelStatus
from app.models.finance import Expense, LedgerAccountType, LedgerEntry
from app.models.team_member import TeamMember, TeamRole
from app.schemas.finance import CashForecastOut, CashForecastPoint, ExpenseCreate, ExpenseOut, FinanceOverview

router = APIRouter(prefix="/finance", tags=["finance"])

PERIOD_KINDS = {"month", "quarter", "year"}
EXPORT_TYPES = {"sales_book", "expenses", "stock_value"}


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    """Parse 'YYYY-MM' (month), 'YYYY-QN' (quarter) or 'YYYY' (year)."""
    if "-Q" in period:
        year_str, q_str = period.split("-Q")
        year, quarter = int(year_str), int(q_str)
        start_month = (quarter - 1) * 3 + 1
        start = datetime(year, start_month, 1, tzinfo=timezone.utc)
        end_month = start_month + 3
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if end_month > 12
            else datetime(year, end_month, 1, tzinfo=timezone.utc)
        )
    elif "-" in period:
        year, month = (int(p) for p in period.split("-"))
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    else:
        year = int(period)
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return start, end


@router.get("/overview", response_model=FinanceOverview)
def finance_overview(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> FinanceOverview:
    shop_id = current_user.shop_id

    sales = (
        db.query(Order)
        .filter(Order.shop_id == shop_id, Order.status != OrderStatus.RETURNED)
        .with_entities(Order.total_amount)
        .all()
    )
    total_sales = sum((s[0] for s in sales), Decimal("0"))

    expenses = db.query(Expense).filter(Expense.shop_id == shop_id).with_entities(Expense.amount).all()
    total_expenses = sum((e[0] for e in expenses), Decimal("0"))

    # FR-FIN-01/02: real COGS from each order item's cost snapshot (see
    # orders.py create_order), for every order that isn't returned.
    cogs_rows = (
        db.query(OrderItem.quantity, OrderItem.unit_cost_snapshot)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.shop_id == shop_id, Order.status != OrderStatus.RETURNED)
        .all()
    )
    cost_of_goods_sold = sum(
        (Decimal(q) * c for q, c in cogs_rows if c is not None), Decimal("0")
    )

    cod_outstanding = (
        db.query(DeliveryParcel)
        .join(Order)
        .filter(
            Order.shop_id == shop_id,
            DeliveryParcel.status == ParcelStatus.DELIVERED,
            DeliveryParcel.cod_remitted.is_(False),
        )
        .with_entities(DeliveryParcel.cod_amount)
        .all()
    )
    total_cod = sum((c[0] for c in cod_outstanding), Decimal("0"))

    # Stock valuation (sum of qty * cost per variant) is computed by the
    # dedicated Finance export job (see FR-FIN-06), not inline here.
    stock_value_total = Decimal("0")

    # FR-FIN-01: cash/bank/wallet position is read from the ledger that
    # /payments/{id}/confirm and /finance/expenses post to automatically.
    ledger_rows = (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.shop_id == shop_id,
            LedgerEntry.account_type.in_(
                [LedgerAccountType.CASH, LedgerAccountType.BANK, LedgerAccountType.WALLET]
            ),
        )
        .with_entities(LedgerEntry.amount)
        .all()
    )
    cash_on_hand = sum((r[0] for r in ledger_rows), Decimal("0"))

    gross_profit = total_sales - cost_of_goods_sold
    net_profit = gross_profit - total_expenses

    return FinanceOverview(
        sales=total_sales,
        cost_of_goods_sold=cost_of_goods_sold,
        gross_profit=gross_profit,
        expenses_total=total_expenses,
        net_profit=net_profit,
        cash_on_hand=cash_on_hand,
        cod_with_couriers=total_cod,
        stock_value_at_cost=stock_value_total,
        net_worth=total_cod + stock_value_total,
    )


@router.get("/cash-forecast", response_model=CashForecastOut)
def cash_forecast(
    days: int = 30,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> CashForecastOut:
    """Simple 4-week cash projection from recent sales/expense run-rate + COD inbound (FR-FIN)."""
    shop_id = current_user.shop_id
    days = max(7, min(days, 90))
    weeks = max(1, days // 7)

    ledger_rows = (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.shop_id == shop_id,
            LedgerEntry.account_type.in_(
                [LedgerAccountType.CASH, LedgerAccountType.BANK, LedgerAccountType.WALLET]
            ),
        )
        .with_entities(LedgerEntry.amount)
        .all()
    )
    starting = sum((r[0] for r in ledger_rows), Decimal("0"))

    since = datetime.now(timezone.utc) - timedelta(days=28)
    sales_rows = (
        db.query(Order.total_amount)
        .filter(Order.shop_id == shop_id, Order.status != OrderStatus.RETURNED, Order.created_at >= since)
        .all()
    )
    expense_rows = (
        db.query(Expense.amount)
        .filter(Expense.shop_id == shop_id, Expense.created_at >= since)
        .all()
    )
    weekly_in = sum((r[0] for r in sales_rows), Decimal("0")) / Decimal(4)
    weekly_out = sum((r[0] for r in expense_rows), Decimal("0")) / Decimal(4)

    cod_rows = (
        db.query(DeliveryParcel.cod_amount)
        .join(Order)
        .filter(
            Order.shop_id == shop_id,
            DeliveryParcel.status == ParcelStatus.DELIVERED,
            DeliveryParcel.cod_remitted.is_(False),
        )
        .all()
    )
    cod_pending = sum((r[0] for r in cod_rows), Decimal("0"))

    points: list[CashForecastPoint] = []
    balance = starting
    for i in range(1, weeks + 1):
        projected_in = weekly_in + (cod_pending / Decimal(weeks) if i == 1 else Decimal("0"))
        projected_out = weekly_out
        net = projected_in - projected_out
        balance = balance + net
        points.append(
            CashForecastPoint(
                label=f"Week {i}",
                projected_in=projected_in.quantize(Decimal("0.01")),
                projected_out=projected_out.quantize(Decimal("0.01")),
                net=net.quantize(Decimal("0.01")),
                running_balance=balance.quantize(Decimal("0.01")),
            )
        )

    return CashForecastOut(starting_cash=starting, horizon_days=days, points=points)


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def record_expense(
    payload: ExpenseCreate,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ExpenseOut:
    expense = Expense(shop_id=current_user.shop_id, **payload.model_dump())
    db.add(expense)
    db.flush()  # populate expense.id (client-side UUID default) before referencing it below

    # FR-FIN-01: post this expense to the books automatically.
    paid_from_account = {
        "cash": LedgerAccountType.CASH,
        "bkash": LedgerAccountType.WALLET,
        "nagad": LedgerAccountType.WALLET,
        "bank": LedgerAccountType.BANK,
        "card": LedgerAccountType.BANK,
    }.get(payload.paid_from.lower(), LedgerAccountType.CASH)
    db.add(
        LedgerEntry(
            shop_id=current_user.shop_id,
            account_type=paid_from_account,
            amount=-expense.amount,
            ref_type="expense",
            ref_id=expense.id,
        )
    )

    db.commit()
    db.refresh(expense)
    return expense


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[ExpenseOut]:
    return (
        db.query(Expense)
        .filter(Expense.shop_id == current_user.shop_id)
        .order_by(Expense.created_at.desc())
        .all()
    )


@router.get("/statements/{period}")
def get_statement(
    period: str,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """FR-FIN-06: monthly ('2026-10'), quarterly ('2026-Q4') or annual ('2026') statement."""
    try:
        start, end = _period_bounds(period)
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Period must look like '2026-10' (month), '2026-Q4' (quarter) or '2026' (year).",
        )

    shop_id = current_user.shop_id
    sales_rows = (
        db.query(Order.total_amount)
        .filter(
            Order.shop_id == shop_id,
            Order.status != OrderStatus.RETURNED,
            Order.created_at >= start,
            Order.created_at < end,
        )
        .all()
    )
    total_sales = sum((r[0] for r in sales_rows), Decimal("0"))

    expense_rows = (
        db.query(Expense.amount)
        .filter(Expense.shop_id == shop_id, Expense.created_at >= start, Expense.created_at < end)
        .all()
    )
    total_expenses = sum((r[0] for r in expense_rows), Decimal("0"))

    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "sales": total_sales,
        "expenses": total_expenses,
        "net_profit": total_sales - total_expenses,
    }


@router.get("/exports/{export_type}")
def export_data(
    export_type: str,
    current_user: TeamMember = Depends(require_role(TeamRole.ADMIN)),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """FR-FIN-06: CSV exports. 'sales_book' and 'expenses' are fully generated here;
    'stock_value' needs the ProductVariant cost join — included as a simple pass."""
    if export_type not in EXPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown export type '{export_type}'")

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if export_type == "sales_book":
        writer.writerow(["order_id", "customer_id", "status", "source_channel", "total_amount", "created_at"])
        orders = db.query(Order).filter(Order.shop_id == current_user.shop_id).order_by(Order.created_at).all()
        for o in orders:
            writer.writerow([o.id, o.customer_id, o.status.value, o.source_channel, o.total_amount, o.created_at])

    elif export_type == "expenses":
        writer.writerow(["id", "category", "amount", "paid_from", "note", "created_at"])
        expenses = db.query(Expense).filter(Expense.shop_id == current_user.shop_id).order_by(Expense.created_at).all()
        for e in expenses:
            writer.writerow([e.id, e.category.value, e.amount, e.paid_from, e.note or "", e.created_at])

    elif export_type == "stock_value":
        from app.models.product import Product, ProductVariant

        writer.writerow(["product_id", "variant_id", "sku", "stock_qty", "cost", "value_at_cost"])
        rows = (
            db.query(ProductVariant, Product)
            .join(Product, ProductVariant.product_id == Product.id)
            .filter(Product.shop_id == current_user.shop_id)
            .all()
        )
        for variant, product in rows:
            cost = product.cost or Decimal("0")
            writer.writerow([product.id, variant.id, variant.sku or "", variant.stock_qty, cost, cost * variant.stock_qty])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={export_type}.csv"},
    )
