"""message_audio_ref_to_text

Revision ID: 20261025_0012
Revises: 20261025_0011
Create Date: 2026-10-25

Facebook CDN photo/audio URLs routinely exceed 500 characters due to signed
query-string params. Widen messages.audio_ref from VARCHAR(500) to TEXT.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261025_0012"
down_revision: Union[str, None] = "20261025_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "messages",
        "audio_ref",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE messages SET audio_ref = LEFT(audio_ref, 500) WHERE LENGTH(audio_ref) > 500")
    op.alter_column(
        "messages",
        "audio_ref",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )
