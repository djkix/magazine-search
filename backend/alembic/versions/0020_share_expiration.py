"""expiration et auteur des liens de partage

Les liens de partage (0017, 0018) n'expiraient pas et ne se révoquaient
pas. Chaque lien porte désormais une date d'expiration, sans laquelle il
n'est plus servi, et son auteur, qui peut le révoquer (un administrateur
peut révoquer tous les liens).

Les liens déjà émis reçoivent 30 jours de validité à compter de la
migration, plutôt que d'être coupés sans préavis.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("articles", "magazines")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("share_created_by_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_share_created_by_id_users",
            table,
            "users",
            ["share_created_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET share_expires_at = now() + interval '30 days' "
                "WHERE share_token IS NOT NULL"
            )
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"fk_{table}_share_created_by_id_users", table, type_="foreignkey")
        op.drop_column(table, "share_created_by_id")
        op.drop_column(table, "share_expires_at")
