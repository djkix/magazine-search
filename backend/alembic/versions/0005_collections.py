"""restructure categories into a two-level category/collection hierarchy

Categories become a pure top-level theme (e.g. "Bricolage"), and a new
Collection entity (e.g. "Que Choisir") groups magazine issues under a title
and belongs to one category. Magazines now point at a collection instead of
a category directly.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_magazines_category_id", table_name="magazines")
    op.drop_column("magazines", "category_id")

    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_collections_category_id", "collections", ["category_id"])

    op.add_column(
        "magazines",
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_magazines_collection_id", "magazines", ["collection_id"])


def downgrade() -> None:
    op.drop_index("ix_magazines_collection_id", table_name="magazines")
    op.drop_column("magazines", "collection_id")

    op.drop_index("ix_collections_category_id", table_name="collections")
    op.drop_table("collections")

    op.add_column(
        "magazines",
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_magazines_category_id", "magazines", ["category_id"])
