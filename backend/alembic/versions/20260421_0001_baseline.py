"""Baseline schema via metadata create_all.

Revision ID: 20260421_0001
Revises:
Create Date: 2026-04-21

For greenfield installs: `alembic upgrade head` creates all tables.
For DBs already bootstrapped with ensure_schema(): `alembic stamp head`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260421_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    # Additive patches (same as bootstrap)
    from sqlalchemy import text

    dialect = bind.dialect.name
    patches = [
        ("messages", "delivery_status", "VARCHAR(40)"),
        ("messages", "delivery_detail", "VARCHAR(250)"),
    ]
    for table, column, col_type in patches:
        if dialect == "sqlite":
            rows = bind.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if column not in {r[1] for r in rows}:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        else:
            exists = bind.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": column},
            ).fetchone()
            if not exists:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def downgrade() -> None:
    # Destructive full drop is intentionally not automated.
    pass
