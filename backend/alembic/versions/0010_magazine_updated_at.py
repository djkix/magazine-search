"""add magazines.updated_at, refreshed on every row change, so admin views
can tell recent activity (e.g. a reprocess/re-queue) apart from the
original scan date - created_at never changes after the initial insert

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "magazines",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.execute("UPDATE magazines SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("magazines", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("magazines", "updated_at")
