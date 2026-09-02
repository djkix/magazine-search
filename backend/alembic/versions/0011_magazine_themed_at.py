"""add magazines.themed_at, set once a theme batch has actually considered
a magazine (whether or not it found a theme), so magazines Gemini couldn't
theme aren't resubmitted - and re-billed against the daily quota - forever

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("magazines", sa.Column("themed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE magazines
        SET themed_at = magazines.updated_at
        WHERE id IN (SELECT magazine_id FROM theme_magazines)
        """
    )


def downgrade() -> None:
    op.drop_column("magazines", "themed_at")
