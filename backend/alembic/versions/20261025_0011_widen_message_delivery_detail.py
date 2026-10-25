"""Widen messages.delivery_detail from VARCHAR(250) to TEXT so a full Meta
Graph API error body is actually diagnosable instead of cutting off mid-
sentence — this was blocking real diagnosis of an intermittent image-send
failure.

Revision ID: 20261025_0011
Revises: 20261025_0010
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261025_0011"
down_revision: Union[str, None] = "20261025_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "messages"
COLUMN = "delivery_detail"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        return  # sqlite has no real VARCHAR length enforcement

    bind.execute(text(f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} TYPE TEXT"))


def downgrade() -> None:
    pass
