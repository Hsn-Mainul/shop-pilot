"""Widen products.photo_url and products.post_link from VARCHAR(500) to TEXT.
Facebook's own CDN photo URLs routinely exceed 500 characters once their
signed query-string parameters are included, which crashed any attempt to
save a live-discovered photo URL back onto a product.

Revision ID: 20261025_0009
Revises: 055c2739bd19
Create Date: 2026-10-25
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20261025_0009"
down_revision: Union[str, None] = "055c2739bd19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "products"
COLUMNS = ["photo_url", "post_link"]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # sqlite has no real VARCHAR length enforcement — nothing to migrate.
        return

    for column in COLUMNS:
        bind.execute(text(f"ALTER TABLE {TABLE} ALTER COLUMN {column} TYPE TEXT"))


def downgrade() -> None:
    pass
