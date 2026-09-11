"""sous-thematiques : un niveau intermediaire entre une thematique et les
numeros, nomme hors ligne par un modele de langage puis rattache localement
aux numeros par correspondance des mots-cles sur les titres d'articles

Les mots-cles sont conserves avec la sous-thematique : c'est eux qui
permettent de RECALCULER les rattachements sans refaire appel a un modele,
notamment quand de nouveaux numeros entrent dans la bibliotheque.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subthemes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "theme_id",
            sa.Integer(),
            sa.ForeignKey("themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        # Les mots-cles qui definissent la sous-thematique. Conserves pour
        # pouvoir rejouer le rattachement a tout moment, gratuitement.
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Deux sous-thematiques homonymes sous la meme thematique n'auraient
        # aucun sens, et rendraient l'import non idempotent : c'est ce couple
        # qui sert de cle de rapprochement lors d'un reimport.
        sa.UniqueConstraint("theme_id", "name", name="uq_subtheme_theme_name"),
    )
    # PostgreSQL n'indexe pas les cles etrangeres : sans cet index, lister les
    # sous-thematiques d'une thematique impose un parcours complet.
    op.create_index("ix_subthemes_theme_id", "subthemes", ["theme_id"])

    op.create_table(
        "subtheme_magazines",
        sa.Column(
            "subtheme_id",
            sa.Integer(),
            sa.ForeignKey("subthemes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "magazine_id",
            sa.Integer(),
            sa.ForeignKey("magazines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # Nombre d'articles du numero correspondant aux mots-cles. C'est le
        # premier critere de tri de la liste affichee, la date departageant
        # les ex aequo.
        sa.Column("occurrences", sa.Integer(), nullable=False),
    )
    # La cle primaire composite n'indexe que sa colonne de tete : le parcours
    # inverse (les sous-thematiques d'un numero) resterait sans index.
    op.create_index(
        "ix_subtheme_magazines_magazine_id", "subtheme_magazines", ["magazine_id"]
    )
    # Sert le tri de la liste finale, (subtheme_id, occurrences decroissantes).
    # Pas de DESC dans la definition : un index B-tree se parcourt dans les
    # deux sens, l'ajouter ne servirait qu'a compliquer la migration.
    op.create_index(
        "ix_subtheme_magazines_subtheme_id_occurrences",
        "subtheme_magazines",
        ["subtheme_id", "occurrences"],
    )


def downgrade() -> None:
    # Les index poses sur ces tables disparaissent avec elles : les supprimer
    # un a un serait redondant. Aucun objet appartenant a une revision
    # anterieure n'est touche ici — c'est precisement l'erreur commise dans
    # 0012, ou le downgrade supprimait un index cree par 0005.
    op.drop_table("subtheme_magazines")
    op.drop_table("subthemes")
