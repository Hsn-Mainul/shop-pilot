"""Add orders.invoice_number (customer-facing shipment-tracking reference) and
a DECLINED order status so a seller can explicitly reject a chat-placed order.

Revision ID: 20261025_0007
Revises: 20261024_0006
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261025_0007"
down_revision: Union[str, None] = "20261024_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "orders"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        rows = bind.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        existing = {r[1] for r in rows}
        if "invoice_number" not in existing:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN invoice_number VARCHAR(50)"))
        # sqlite has no native enum type — OrderStatus.DECLINED just works as a new string value.
    else:
        exists = bind.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": TABLE, "c": "invoice_number"},
        ).fetchone()
        if not exists:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN invoice_number VARCHAR(50)"))
        bind.execute(
            text(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{TABLE}_invoice_number ON {TABLE} (invoice_number)")
        )
        # Postgres native enum: add the new value if it isn't already there. SQLAlchemy's
        # Enum() stores the Python member *name* (not .value) by default, and the existing
        # values here are all upper-case (NEW, CONFIRMED, ...), so this must match that case.
        # ALTER TYPE ... ADD VALUE cannot run inside the same transaction as its use,
        # but can run standalone, which is how Alembic executes each migration here.
        bind.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'DECLINED'"))


def downgrade() -> None:
    pass
