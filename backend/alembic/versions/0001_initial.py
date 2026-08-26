"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scan_status = sa.Enum(
        "detected", "stable", "queued", "processing", "done", "failed", name="scan_status"
    )
    ocr_status = sa.Enum("pending", "processing", "done", "failed", name="ocr_status")
    page_language = sa.Enum("fr", "en", "mixed", name="page_language")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "magazines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("issue_number", sa.String(50), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_mtime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cover_thumbnail_path", sa.String(1000), nullable=True),
        sa.Column("scan_status", scan_status, nullable=False, server_default="detected"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_magazines_file_hash", "magazines", ["file_hash"])

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "magazine_id",
            sa.Integer(),
            sa.ForeignKey("magazines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("language", page_language, nullable=True),
        sa.Column("words", sa.JSON(), nullable=True),
        sa.Column("ocr_status", ocr_status, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("magazine_id", "page_number", name="uq_page_magazine_number"),
    )


def downgrade() -> None:
    op.drop_table("pages")
    op.drop_table("magazines")
    op.drop_table("users")
    sa.Enum(name="page_language").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ocr_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scan_status").drop(op.get_bind(), checkfirst=True)
