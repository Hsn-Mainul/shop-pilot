"""Add discount_percent and min_negotiable_price to products, so the AI chat
assistant can offer/negotiate a discount in a bounded, seller-controlled way.

Revision ID: 20261025_0008
Revises: 20261025_0007
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261025_0008"
down_revision: Union[str, None] = "20261025_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "products"
COLUMNS = [
    ("discount_percent", "NUMERIC(5,2)"),
    ("min_negotiable_price", "NUMERIC(12,2)"),
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        rows = bind.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        existing = {r[1] for r in rows}
        for column, col_type in COLUMNS:
            if column not in existing:
                bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {column} {col_type}"))
    else:
        for column, col_type in COLUMNS:
            exists = bind.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": TABLE, "c": column},
            ).fetchone()
            if not exists:
                bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {column} {col_type}"))


def downgrade() -> None:
    pass
