"""ajouter share_token aux articles pour le partage par lien

Permet de partager un article precis via un lien public, sans compte :
voir docs/superpowers/specs/2026-10-07-partage-article-design.md. La
colonne est nullable (la quasi-totalite des articles ne sont jamais
partages) et generee a la demande, pas a l'extraction du sommaire.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("share_token", sa.String(length=43), nullable=True))
    op.create_index("ix_articles_share_token", "articles", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_articles_share_token", table_name="articles")
    op.drop_column("articles", "share_token")
