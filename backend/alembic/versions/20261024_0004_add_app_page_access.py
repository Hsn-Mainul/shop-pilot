"""Add app_page_visibility and app_page_user_permissions tables for
System Admin control over OUR OWN application pages/modules (Setup,
Integrations, Products, ...) — distinct from social media Page visibility.

Revision ID: 20261024_0004
Revises: 20261024_0003
Create Date: 2026-10-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261024_0004"
down_revision: Union[str, None] = "20261024_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect != "sqlite" else sa.String(36)

    existing_tables = sa.inspect(bind).get_table_names()

    if "app_page_visibility" not in existing_tables:
        op.create_table(
            "app_page_visibility",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("page_key", sa.String(80), nullable=False, unique=True),
            sa.Column("is_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_app_page_visibility_page_key", "app_page_visibility", ["page_key"])

    if "app_page_user_permissions" not in existing_tables:
        op.create_table(
            "app_page_user_permissions",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("page_key", sa.String(80), nullable=False),
            sa.Column("user_id", uuid_type, sa.ForeignKey("team_members.id"), nullable=False),
            sa.UniqueConstraint("page_key", "user_id", name="uq_app_page_user_permission"),
        )
        op.create_index("ix_app_page_user_permissions_page_key", "app_page_user_permissions", ["page_key"])
        op.create_index("ix_app_page_user_permissions_user_id", "app_page_user_permissions", ["user_id"])


def downgrade() -> None:
    pass
