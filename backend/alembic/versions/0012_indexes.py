"""Index sur les colonnes réellement filtrées, triées et jointes

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-10

Jusqu'ici seuls `users.email` et `magazines.file_hash` étaient indexés, tous
deux comme effet de bord d'une contrainte d'unicité. Tout le reste des accès
se faisait en parcours séquentiel — acceptable sur une centaine de numéros,
plus du tout au-delà du millier.

Point à connaître : **PostgreSQL ne crée aucun index sur les clés
étrangères**. `pages.magazine_id`, sur la plus grosse table de la base,
n'en avait donc pas, alors que chaque affichage de numéro la parcourt.

Les index composites sont ordonnés pour servir à la fois le filtre et le tri
qui l'accompagne systématiquement dans le code (`filter(magazine_id)` puis
`order_by(page_number)`), et ils couvrent aussi les recherches portant sur
la seule première colonne.

Verrouillage : `CREATE INDEX` prend un verrou SHARE, qui bloque les écritures
mais laisse les lectures passer. À lancer file d'ingestion vide, et après un
dump — voir ops/pg_backup.sh. La variante CONCURRENTLY, non bloquante, n'est
pas utilisable ici : elle ne peut pas s'exécuter dans la transaction dont
Alembic enveloppe la migration.
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- pages : la plus grosse table, jointe à chaque consultation ---
    op.create_index("ix_pages_magazine_id_page_number", "pages", ["magazine_id", "page_number"])

    # --- articles : sommaire d'un numéro, et sous-requête « sans article » ---
    op.create_index("ix_articles_magazine_id_start_page", "articles", ["magazine_id", "start_page"])

    # --- magazines : filtres du tableau de bord et de la bibliothèque ---
    # scan_status est relu toutes les 5 secondes par le tableau de bord.
    op.create_index("ix_magazines_scan_status", "magazines", ["scan_status"])
    op.create_index("ix_magazines_collection_id", "magazines", ["collection_id"])
    op.create_index("ix_magazines_publication_date", "magazines", ["publication_date"])
    # toc_status et themed_at pilotent la file de thématisation et le
    # décompte des numéros sans sommaire.
    op.create_index("ix_magazines_toc_status", "magazines", ["toc_status"])
    op.create_index("ix_magazines_themed_at", "magazines", ["themed_at"])

    # --- tables d'association : le sens inverse de la clé primaire ---
    # La PK composite (collection_id, tag_id) n'indexe que collection_id ;
    # or le filtrage par tag part de tag_id.
    op.create_index("ix_collection_tags_tag_id", "collection_tags", ["tag_id"])
    # Idem : PK (theme_id, magazine_id), mais on interroge par magazine.
    op.create_index("ix_theme_magazines_magazine_id", "theme_magazines", ["magazine_id"])

    # --- recherche de thème insensible à la casse ---
    # Le code compare `func.lower(Theme.name)` : un index ordinaire sur name
    # ne peut pas être utilisé, il faut un index fonctionnel sur l'expression.
    op.create_index("ix_themes_lower_name", "themes", [sa.text("lower(name)")])


def downgrade() -> None:
    op.drop_index("ix_themes_lower_name", table_name="themes")
    op.drop_index("ix_theme_magazines_magazine_id", table_name="theme_magazines")
    op.drop_index("ix_collection_tags_tag_id", table_name="collection_tags")
    op.drop_index("ix_magazines_themed_at", table_name="magazines")
    op.drop_index("ix_magazines_toc_status", table_name="magazines")
    op.drop_index("ix_magazines_publication_date", table_name="magazines")
    op.drop_index("ix_magazines_collection_id", table_name="magazines")
    op.drop_index("ix_magazines_scan_status", table_name="magazines")
    op.drop_index("ix_articles_magazine_id_start_page", table_name="articles")
    op.drop_index("ix_pages_magazine_id_page_number", table_name="pages")
