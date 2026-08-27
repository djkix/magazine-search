"""add articles table and magazine TOC status

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    toc_status = sa.Enum("pending", "processing", "done", "failed", name="toc_status")
    toc_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "magazines",
        sa.Column("toc_status", toc_status, nullable=False, server_default="pending"),
    )
    op.add_column("magazines", sa.Column("toc_error_message", sa.Text(), nullable=True))

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "magazine_id",
            sa.Integer(),
            sa.ForeignKey("magazines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_articles_magazine_id", "articles", ["magazine_id"])


def downgrade() -> None:
    op.drop_table("articles")
    op.drop_column("magazines", "toc_error_message")
    op.drop_column("magazines", "toc_status")
    sa.Enum(name="toc_status").drop(op.get_bind(), checkfirst=True)
