import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.finance import ExpenseCategory


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    amount: Decimal
    paid_from: str
    note: str | None = None
    receipt_photo_url: str | None = None


class ExpenseOut(ExpenseCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class FinanceOverview(BaseModel):
    sales: Decimal
    cost_of_goods_sold: Decimal
    gross_profit: Decimal
    expenses_total: Decimal
    net_profit: Decimal
    cash_on_hand: Decimal
    cod_with_couriers: Decimal
    stock_value_at_cost: Decimal
    net_worth: Decimal


class CashForecastPoint(BaseModel):
    label: str
    projected_in: Decimal
    projected_out: Decimal
    net: Decimal
    running_balance: Decimal


class CashForecastOut(BaseModel):
    starting_cash: Decimal
    horizon_days: int
    points: list[CashForecastPoint]
