"""Add messages.external_message_id so a redelivered webhook event (Meta
commonly sends the same message at-least-once) or a customer double-send of
the same attachment can be recognized and skipped, instead of running a full
fresh AI reply (vision + LLM calls) for an exact repeat.

Revision ID: 20261025_0010
Revises: 20261025_0009
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261025_0010"
down_revision: Union[str, None] = "20261025_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "messages"
COLUMN = "external_message_id"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        rows = bind.execute(text(f"PRAGMA table_info({TABLE})")).fetchall()
        existing = {r[1] for r in rows}
        if COLUMN not in existing:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(255)"))
    else:
        exists = bind.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": TABLE, "c": COLUMN},
        ).fetchone()
        if not exists:
            bind.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(255)"))
        bind.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_{COLUMN} ON {TABLE} ({COLUMN})")
        )


def downgrade() -> None:
    pass
