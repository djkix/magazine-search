"""distinguer les tags de SUJET (Bricolage, Sante) des tags de FORMAT
editorial (Test, Tutoriel, Guide Achat), pour ne propager en thematiques que
les premiers

Un tag est pose a la main sur une COLLECTION entiere : c'est une donnee curee,
donc plus sure qu'une inference de modele. Mais le vocabulaire melange deux
natures. Propager les cinq tags de « Systeme D » donnerait une page ou « Test »
et « Tutoriel » ecraseraient tout, ce qui ne veut rien dire pour naviguer par
sujet.

DEFAUT A FAUX, deliberement : aucun tag existant ne devient sujet du seul fait
de la migration. Le choix revient a l'administrateur, tag par tag. L'inverse
aurait pollue la page des la mise a jour, sans que personne ne l'ait demande.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default pose la valeur sur toutes les lignes existantes, ce qui
    # est ICI le comportement voulu : tout a faux. Pas de backfill a suivre,
    # donc pas le piege de 0010, dont le UPDATE conditionnel ne trouvait
    # aucune ligne justement parce que le defaut serveur avait deja rempli la
    # colonne.
    op.add_column(
        "tags",
        sa.Column("is_subject", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tags", "is_subject")
