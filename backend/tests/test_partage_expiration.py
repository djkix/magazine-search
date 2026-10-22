"""Expiration et révocation des liens de partage.

Un lien porte une date d'expiration (30 jours par défaut) au-delà de
laquelle il n'est plus servi, et peut être révoqué par son auteur ou par un
administrateur. Base SQLite en mémoire, aucun autre service.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import get_current_admin, get_current_user
from app.main import app
from app.models import Article, Magazine, User

UTC = datetime.timezone.utc


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def comptes(db_session):
    auteur = User(email="auteur@exemple.fr", display_name="Auteur", password_hash="h", is_active=True)
    autre = User(email="autre@exemple.fr", display_name="Autre", password_hash="h", is_active=True)
    admin = User(email="admin@exemple.fr", display_name="Admin", password_hash="h", is_active=True, is_admin=True)
    db_session.add_all([auteur, autre, admin])
    db_session.commit()
    return {"auteur": auteur, "autre": autre, "admin": admin}


@pytest.fixture
def connecte(db_session, comptes):
    """`connecte("auteur")` : les requêtes suivantes sont faites sous ce compte."""

    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db

    def _choisir(nom):
        app.dependency_overrides[get_current_user] = lambda: comptes[nom]
        if comptes[nom].is_admin:
            app.dependency_overrides[get_current_admin] = lambda: comptes[nom]
        else:
            app.dependency_overrides.pop(get_current_admin, None)

    _choisir("auteur")
    yield _choisir
    app.dependency_overrides.clear()


@pytest.fixture
def client(connecte):
    return TestClient(app)


@pytest.fixture
def article(db_session):
    magazine = Magazine(
        title="Numéro test",
        filename="t.pdf",
        file_path="t.pdf",
        file_hash="h1",
        file_size=1,
        file_mtime=datetime.datetime.now(UTC),
    )
    db_session.add(magazine)
    db_session.commit()
    a = Article(magazine_id=magazine.id, title="Un article", start_page=2)
    db_session.add(a)
    db_session.commit()
    return a


def _expirer(db_session, instance):
    instance.share_expires_at = datetime.datetime.now(UTC) - datetime.timedelta(minutes=1)
    db_session.commit()


def test_lien_cree_avec_expiration_par_defaut(client, article):
    corps = client.post(f"/api/articles/{article.id}/share").json()

    expire = datetime.datetime.fromisoformat(corps["expires_at"]).replace(tzinfo=UTC)
    ecart = expire - datetime.datetime.now(UTC)
    assert datetime.timedelta(days=29) < ecart <= datetime.timedelta(days=30)


def test_duree_choisie(client, article):
    corps = client.post(f"/api/articles/{article.id}/share", json={"days": 7}).json()

    expire = datetime.datetime.fromisoformat(corps["expires_at"]).replace(tzinfo=UTC)
    assert expire - datetime.datetime.now(UTC) <= datetime.timedelta(days=7)


def test_duree_au_dela_du_plafond_refusee(client, article):
    assert client.post(f"/api/articles/{article.id}/share", json={"days": 10_000}).status_code == 422
    assert client.post(f"/api/articles/{article.id}/share", json={"days": 0}).status_code == 422


def test_lien_expire_n_est_plus_servi(client, article, db_session):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    _expirer(db_session, article)

    assert client.get(f"/api/partage/{token}").status_code == 404
    assert client.get(f"/api/partage/{token}/cover").status_code == 404
    assert client.get(f"/api/partage/{token}/file").status_code == 404


def test_lien_sans_expiration_n_est_jamais_servi(client, article, db_session):
    """Échec fermé : un jeton posé sans date (donnée héritée, bug) est refusé."""
    article.share_token = "jeton-sans-date-d-expiration-0000000000000"
    db_session.commit()

    assert client.get(f"/api/partage/{article.share_token}").status_code == 404


def test_repartager_apres_expiration_donne_un_nouveau_jeton(client, article, db_session):
    ancien = client.post(f"/api/articles/{article.id}/share").json()["token"]
    _expirer(db_session, article)

    nouveau = client.post(f"/api/articles/{article.id}/share").json()["token"]

    assert nouveau != ancien
    assert client.get(f"/api/partage/{ancien}").status_code == 404
    assert client.get(f"/api/partage/{nouveau}").status_code == 200


def test_auteur_revoque_son_lien(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]

    assert client.delete(f"/api/articles/{article.id}/share").status_code == 204
    assert client.get(f"/api/partage/{token}").status_code == 404
    # Un nouveau partage ne ressuscite jamais l'ancien jeton.
    assert client.post(f"/api/articles/{article.id}/share").json()["token"] != token


def test_autre_utilisateur_ne_peut_pas_revoquer(client, connecte, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]

    connecte("autre")

    assert client.delete(f"/api/articles/{article.id}/share").status_code == 403
    assert client.get(f"/api/partage/{token}").status_code == 200


def test_admin_revoque_n_importe_quel_lien(client, connecte, article):
    token = client.post(f"/api/magazines/{article.magazine_id}/share").json()["token"]

    connecte("admin")

    assert client.delete(f"/api/magazines/{article.magazine_id}/share").status_code == 204
    assert client.get(f"/api/partage/magazine/{token}").status_code == 404


def test_lien_herite_sans_auteur_reserve_a_l_admin(client, connecte, article, db_session):
    client.post(f"/api/articles/{article.id}/share")
    article.share_created_by_id = None
    db_session.commit()

    assert client.delete(f"/api/articles/{article.id}/share").status_code == 403
    connecte("admin")
    assert client.delete(f"/api/articles/{article.id}/share").status_code == 204


def test_revoquer_sans_lien_404(client, article):
    assert client.delete(f"/api/articles/{article.id}/share").status_code == 404


def test_liste_admin_des_liens_actifs(client, connecte, article, db_session):
    client.post(f"/api/articles/{article.id}/share")
    client.post(f"/api/magazines/{article.magazine_id}/share", json={"days": 3})
    connecte("admin")

    liens = client.get("/api/admin/partages").json()

    assert [(lien["kind"], lien["created_by_email"]) for lien in liens] == [
        ("magazine", "auteur@exemple.fr"),
        ("article", "auteur@exemple.fr"),
    ]

    _expirer(db_session, article)
    assert [lien["kind"] for lien in client.get("/api/admin/partages").json()] == ["magazine"]
