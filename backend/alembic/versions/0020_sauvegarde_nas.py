"""sauvegarde vers le NAS : tentatives et demandes

`backup_runs` reçoit une ligne par tentative, écrite par le service
`sauvegarde` ; le tableau de bord d'administration en tire l'alerte (échec,
ou rien de réussi depuis 36 h). `backup_requests` porte le bouton
« Sauvegarder maintenant ». Ajout seulement.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_backup_runs_finished_at", "backup_runs", ["finished_at"])
    op.create_table(
        "backup_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backup_requests")
    op.drop_index("ix_backup_runs_finished_at", table_name="backup_runs")
    op.drop_table("backup_runs")
