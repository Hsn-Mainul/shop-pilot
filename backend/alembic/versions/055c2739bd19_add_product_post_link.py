"""add_product_post_link

Revision ID: 055c2739bd19
Revises: 20261025_0008
Create Date: 2026-10-25 00:57:36.251438

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055c2739bd19"
down_revision: Union[str, None] = "20261025_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("post_link", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "post_link")
