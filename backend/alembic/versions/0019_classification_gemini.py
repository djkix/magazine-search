"""classification des orphelins par Gemini : origine des liens et horodatage

`subtheme_articles.source` distingue les liens calculés par mots-clés
(recalculables) de ceux posés par le modèle, que le recalcul ne doit pas
effacer. `articles.classe_par_gemini_le` empêche de renvoyer au modèle un
article déjà soumis, qu'il ait été rattaché ou non.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subtheme_articles",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="mots_cles"),
    )
    op.add_column(
        "articles", sa.Column("classe_par_gemini_le", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("articles", "classe_par_gemini_le")
    op.drop_column("subtheme_articles", "source")
