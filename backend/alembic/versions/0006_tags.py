"""rename categories to tags with a many-to-many collection relationship,
add magazine issue_type (normal/hs/sp) with a heuristic backfill

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("categories", "tags")

    op.create_table(
        "collection_tags",
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute(
        "INSERT INTO collection_tags (collection_id, tag_id) "
        "SELECT id, category_id FROM collections WHERE category_id IS NOT NULL"
    )

    op.drop_index("ix_collections_category_id", table_name="collections")
    op.drop_column("collections", "category_id")

    issue_type = sa.Enum("normal", "hs", "sp", name="issue_type")
    issue_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "magazines",
        sa.Column("issue_type", issue_type, nullable=False, server_default="normal"),
    )

    # Best-effort heuristic for magazines already in the library, matching
    # the same keyword logic applied to newly-scanned files going forward.
    op.execute(
        r"UPDATE magazines SET issue_type = 'hs' "
        r"WHERE title ~* '\mhors[- ]s[ée]rie\M' OR title ~* '\mhs\M'"
    )
    op.execute(
        r"UPDATE magazines SET issue_type = 'sp' "
        r"WHERE issue_type = 'normal' AND (title ~* '\msp[ée]cial\M' OR title ~* '\msp\M')"
    )


def downgrade() -> None:
    op.drop_column("magazines", "issue_type")
    sa.Enum(name="issue_type").drop(op.get_bind(), checkfirst=True)

    op.add_column(
        "collections",
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="SET NULL"), nullable=True),
    )
    op.execute(
        "UPDATE collections SET category_id = ("
        "SELECT tag_id FROM collection_tags WHERE collection_tags.collection_id = collections.id LIMIT 1"
        ")"
    )
    op.create_index("ix_collections_category_id", "collections", ["category_id"])

    op.drop_table("collection_tags")

    op.rename_table("tags", "categories")
