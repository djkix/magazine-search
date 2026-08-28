"""add issue_month_label, for display of a magazine's month or month range
(issue_number and publication_date columns already existed but were never
populated - this just adds the missing display column, backfilling both
happens via the existing "recalculate" admin maintenance action)

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("magazines", sa.Column("issue_month_label", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("magazines", "issue_month_label")
