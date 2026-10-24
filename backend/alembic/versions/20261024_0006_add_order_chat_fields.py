"""Add conversation_id, customer_phone, delivery_address to orders so an AI
chat-confirmed order can be traced back to its conversation (and never
duplicated), and carry the phone/address the customer gave in chat.

Revision ID: 20261024_0006
Revises: 20261024_0005
Create Date: 2026-10-24
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261024_0006"
down_revision: Union[str, None] = "20261024_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "orders"
COLUMNS = [
    ("conversation_id", "UUID"),
    ("customer_phone", "VARCHAR(50)"),
    ("delivery_address", "VARCHAR(500)"),
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        rows = bind.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        existing = {r[1] for r in rows}
        for column, col_type in COLUMNS:
            if column not in existing:
                sqlite_type = "VARCHAR(36)" if col_type == "UUID" else col_type
                bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {column} {sqlite_type}"))
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
        bind.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_conversation_id ON {TABLE} (conversation_id)")
        )


def downgrade() -> None:
    pass
