"""Add page_id column to ai_credit_ledger_entries for per-page usage tracking.

Revision ID: 20261024_0003
Revises: 20261023_0002
Create Date: 2026-10-24
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261024_0003"
down_revision: Union[str, None] = "20261023_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "ai_credit_ledger_entries"
COLUMN = "page_id"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        rows = bind.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        existing = {r[1] for r in rows}
        if COLUMN not in existing:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(120)"))
    else:
        exists = bind.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": TABLE, "c": COLUMN},
        ).fetchone()
        if not exists:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(120)"))
            bind.execute(
                text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_{COLUMN} ON {TABLE} ({COLUMN})")
            )


def downgrade() -> None:
    pass
