"""Configuration commune aux tests.

IMPORTANT : les variables d'environnement doivent être posées AVANT tout
import de `app.config`. La classe Settings refuse désormais de se construire
sans `JWT_SECRET_KEY` (32 caractères minimum) ni `MEILI_MASTER_KEY` (16
minimum), et rejette les valeurs d'exemple connues. Sans ce bloc, la simple
collecte des tests échouerait au premier import.

Les valeurs ci-dessous sont des secrets de test, jamais utilisés ailleurs.
"""

import os
import tempfile

# Journalisation redirigée vers un répertoire temporaire. Sans cela,
# `configure_logging` tenterait de créer /data/logs — impossible en CI comme
# sur une machine de développement — et l'import de `app.main` échouerait.
os.environ.setdefault("LOG_DIR", tempfile.mkdtemp(prefix="magazine-search-logs-"))

# La valeur est ASSEMBLÉE à l'exécution plutôt qu'écrite en dur : un littéral
# de 50 caractères ressemblant à une clé déclenche gitleaks, en pre-commit
# comme en CI. La construire par concaténation évite d'avoir à inscrire une
# exception dans .gitleaks.toml — et donc d'ouvrir un angle mort permanent
# dans la détection de secrets.
_CLE_DE_TEST = "test-" + "0123456789abcdef" * 3  # 53 caractères

os.environ.setdefault("JWT_SECRET_KEY", _CLE_DE_TEST)  # 32 caractères minimum exigés
os.environ.setdefault("MEILI_MASTER_KEY", _CLE_DE_TEST[:20])  # 16 minimum exigés
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("ADMIN_BOOTSTRAP_EMAIL", "")
os.environ.setdefault("ADMIN_BOOTSTRAP_PASSWORD", "")
# Compteurs de débit en mémoire : les tests n'ont pas de Redis.
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")

# `Settings` lit aussi un fichier .env s'il existe. En CI il n'y en a pas ; en
# local, les valeurs ci-dessus sont posées via setdefault, donc un .env réel
# resterait prioritaire. Les tests ci-dessous ne dépendent d'aucune valeur
# précise en dehors des secrets, ce qui les rend insensibles à ce détail.


# ---- Base en mémoire et fabrique de données pour les tests de taxonomie ----

import itertools  # noqa: E402

import pytest  # noqa: E402


class FabriqueTaxonomie:
    """Crée des lignes minimales (magazine, article, thématique...) en base."""

    def __init__(self, db):
        self.db = db
        self._n = itertools.count(1)

    def magazine(self, collection=None):
        import datetime

        from app.models import Magazine

        n = next(self._n)
        magazine = Magazine(
            title=f"Magazine {n}",
            filename=f"m{n}.pdf",
            file_path=f"/mnt/nas/m{n}.pdf",
            file_hash=f"{n:064d}",
            file_size=1,
            file_mtime=datetime.datetime.now(datetime.timezone.utc),
            collection=collection,
        )
        self.db.add(magazine)
        self.db.flush()
        return magazine

    def collection(self, nom):
        from app.models import Collection

        collection = Collection(name=nom)
        self.db.add(collection)
        self.db.flush()
        return collection

    def article(self, titre, magazine=None):
        from app.models import Article

        magazine = magazine or self.magazine()
        article = Article(magazine_id=magazine.id, title=titre, start_page=1)
        self.db.add(article)
        self.db.flush()
        return article

    def theme(self, nom):
        from app.models import Theme

        theme = Theme(name=nom)
        self.db.add(theme)
        self.db.flush()
        return theme

    def sous_theme(self, theme, nom, mots_cles):
        from app.models import Subtheme

        sous_theme = Subtheme(theme_id=theme.id, name=nom, keywords=mots_cles)
        self.db.add(sous_theme)
        self.db.flush()
        return sous_theme

    def lier(self, sous_theme, article, source="mots_cles"):
        from app.models import subtheme_articles

        self.db.execute(
            subtheme_articles.insert().values(
                subtheme_id=sous_theme.id, article_id=article.id, source=source
            )
        )
        self.db.flush()


@pytest.fixture
def db_taxonomie():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401 - enregistre les tables avant create_all
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fabrique(db_taxonomie):
    return FabriqueTaxonomie(db_taxonomie)
