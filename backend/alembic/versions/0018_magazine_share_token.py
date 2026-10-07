"""ajouter share_token aux magazines pour le partage d'un numero entier

Complement au partage d'article (0017) : celui-ci donne acces a un numero
entier, pas seulement a un article precis. Meme mecanisme, colonne
distincte - un numero et l'un de ses articles peuvent etre partages
independamment, avec des liens differents.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("magazines", sa.Column("share_token", sa.String(length=43), nullable=True))
    op.create_index("ix_magazines_share_token", "magazines", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_magazines_share_token", table_name="magazines")
    op.drop_column("magazines", "share_token")
