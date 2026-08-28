"""replace the manual per-collection Gemini theme summary with automatic
per-magazine themes (generated once at indexing time, shared name
vocabulary across the library, many-to-many with Magazine)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("collection_theme_summaries")

    op.create_table(
        "themes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "theme_magazines",
        sa.Column("theme_id", sa.Integer(), sa.ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("magazine_id", sa.Integer(), sa.ForeignKey("magazines.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("theme_magazines")
    op.drop_table("themes")

    op.create_table(
        "collection_theme_summaries",
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("themes", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
