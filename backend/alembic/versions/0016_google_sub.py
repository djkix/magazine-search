"""ajouter google_sub aux utilisateurs pour la connexion "Se connecter avec
Google"

Nouvelle méthode de connexion par jeton d'identité Google (Google Identity
Services), en plus de l'email+mot de passe existant. La colonne stocke
l'identifiant de sujet stable renvoyé par Google ("sub"), pour mémoire une
fois qu'une connexion via Google a eu lieu — mais le rattachement d'un
compte à un login Google se fait par EMAIL, pas par cette colonne : un
compte créé à la main par un administrateur et un login Google ultérieur
avec le même email doivent fusionner sur la même ligne, jamais créer un
doublon. Nullable : la quasi-totalité des comptes existants ne sont jamais
passés par Google et n'en auront jamais besoin.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
