"""Add embedding JSONB column to ai_knowledge_items and products for Ollama RAG.

Revision ID: 20261023_0002
Revises: 20260421_0001
Create Date: 2026-10-23
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261023_0002"
down_revision: Union[str, None] = "20260421_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    col_type = "JSON" if dialect == "sqlite" else "JSONB"

    for table in ("ai_knowledge_items", "products"):
        if dialect == "sqlite":
            rows = bind.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {r[1] for r in rows}
            if "embedding" not in existing:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN embedding {col_type}"))
        else:
            exists = bind.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = 'embedding'"
                ),
                {"t": table},
            ).fetchone()
            if not exists:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN embedding {col_type}"))


def downgrade() -> None:
    pass
