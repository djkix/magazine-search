"""rattacher les sous-thematiques aux ARTICLES et non plus aux numeros

Le modele precedent liait une sous-thematique a un numero entier. C'etait la
mauvaise granularite : « Les legumes, bientot une denree de luxe » est UN
article, page 6, et c'est lui qui releve de « Alimentation > legumes » — pas
les vingt autres titres du meme numero.

Cette confusion produisait une contamination mesurable : un numero de
« 60 Millions » etiquete [Consommation, Sante, Animaux] versait ses vingt
titres dans les trois corpus d'export, au point que le fichier « Animaux »
parlait surtout de soins dentaires et de chardonnay.

La table subtheme_magazines est SUPPRIMEE plutot que migree : elle n'a jamais
recu de donnees, aucun import n'ayant ete realise.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("subtheme_magazines")

    op.create_table(
        "subtheme_articles",
        sa.Column(
            "subtheme_id",
            sa.Integer(),
            sa.ForeignKey("subthemes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    # La cle primaire composite n'indexe que sa colonne de tete : sans celui-ci,
    # remonter les sous-thematiques d'un article imposerait un parcours complet.
    op.create_index("ix_subtheme_articles_article_id", "subtheme_articles", ["article_id"])


def downgrade() -> None:
    op.drop_table("subtheme_articles")

    # Retablie a l'identique de 0013, pour que la chaine reste rejouable dans
    # les deux sens — ce que le job CI verifie a chaque passage.
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
        sa.Column("occurrences", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_subtheme_magazines_magazine_id", "subtheme_magazines", ["magazine_id"]
    )
    op.create_index(
        "ix_subtheme_magazines_subtheme_id_occurrences",
        "subtheme_magazines",
        ["subtheme_id", "occurrences"],
    )
