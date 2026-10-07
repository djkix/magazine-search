"""Partage d'un article par lien public, sans compte.

Vérifie trois choses : la création du token est idempotente (section 2 de
la conception), et les routes publiques (ajoutées en Task 4) ne dépendent
d'aucune session — elles ne sont pas encore testées ici, seule la création
authentifiée l'est dans cette première tâche.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import get_current_user
from app.main import app
from app.models import Article, Magazine, User


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False : TestClient execute la requete
    # dans un thread different de celui du test, et une connexion SQLite en
    # memoire n'est pas partagee entre threads par defaut — sans ca, le
    # thread de la requete verrait une base vide (ou plantiat au rollback).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _get_db():
        yield db_session

    def _utilisateur():
        u = User()
        u.id = 1
        u.email = "utilisateur@exemple.fr"
        u.display_name = "Utilisateur"
        u.is_admin = False
        u.is_active = True
        u.password_hash = "hash-non-utilise-ici"
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _utilisateur
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def article(db_session):
    magazine = Magazine(
        title="Test",
        filename="test.pdf",
        file_path="test.pdf",
        file_hash="h1",
        file_size=1000,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(magazine)
    db_session.commit()
    a = Article(magazine_id=magazine.id, title="Un article", start_page=5, end_page=7)
    db_session.add(a)
    db_session.commit()
    return a


def test_creation_du_partage_genere_un_token(client, article):
    reponse = client.post(f"/api/articles/{article.id}/share")

    assert reponse.status_code == 200
    assert len(reponse.json()["token"]) > 20


def test_deux_appels_renvoient_le_meme_token(client, article):
    premier = client.post(f"/api/articles/{article.id}/share").json()["token"]
    second = client.post(f"/api/articles/{article.id}/share").json()["token"]

    assert premier == second


def test_article_inconnu_404(client):
    reponse = client.post("/api/articles/999999/share")

    assert reponse.status_code == 404


def test_course_entre_deux_partages_concurrents(client, article, db_session, monkeypatch):
    """Simule une course : share_token est pose par une autre requete juste
    avant que celle-ci ne commite le sien. La mise a jour conditionnelle
    (WHERE share_token IS NULL) doit empecher l'ecrasement, et l'appelant
    doit recevoir le token reellement enregistre, jamais celui qu'il avait
    genere localement avant de perdre la course."""
    import app.routers.articles as articles_module

    token_gagnant = "token-gagnant-de-la-course"

    def faux_token_urlsafe(n):
        # Au moment ou CE thread genere son jeton, un autre a deja gagne et
        # pose le sien directement en base - on le simule ici.
        db_session.query(Article).filter(Article.id == article.id).update(
            {"share_token": token_gagnant}
        )
        db_session.commit()
        return "token-perdant-genere-en-parallele"

    monkeypatch.setattr(articles_module.secrets, "token_urlsafe", faux_token_urlsafe)

    reponse = client.post(f"/api/articles/{article.id}/share")

    assert reponse.json()["token"] == token_gagnant


def test_metadonnees_token_inconnu_404(client):
    reponse = client.get("/api/partage/un-token-qui-n-existe-pas")

    assert reponse.status_code == 404


def test_metadonnees_token_valide(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]

    reponse = client.get(f"/api/partage/{token}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["article_title"] == "Un article"
    assert corps["magazine_title"] == "Test"
    assert corps["start_page"] == 5
    assert corps["end_page"] == 7


def test_metadonnees_accessible_sans_authentification(client, article):
    """Preuve que la route est reellement publique : aucun override de
    get_current_user n'est pose, contrairement au fixture `client` pour les
    autres tests de ce fichier — si la route exigeait une session, elle
    echouerait ici avec 401 plutot que de repondre normalement."""
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}")

    assert reponse.status_code == 200


def test_fichier_sert_le_pdf_par_plages(client, article, db_session, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "processed_dir", str(tmp_path))
    (tmp_path / f"{article.magazine_id}.pdf").write_bytes(b"%PDF-1.4\n" + b"A" * 991)

    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/file", headers={"Range": "bytes=0-9"})

    assert reponse.status_code == 206
    assert reponse.headers["accept-ranges"] == "bytes"
    assert reponse.content == b"%PDF-1.4\nA"


def test_metadonnees_une_seule_requete_sql(client, article, db_session):
    """Avant la jointure explicite, chaque appel faisait 3 aller-retours DB
    (article, puis magazine, puis collection, via le lazy-loading
    SQLAlchemy) sur un endpoint public potentiellement a fort trafic."""
    from sqlalchemy import event

    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    requetes_select = []

    def compter(conn, cursor, statement, *args, **kwargs):
        if statement.strip().upper().startswith("SELECT"):
            requetes_select.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", compter)
    try:
        reponse = client.get(f"/api/partage/{token}")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", compter)

    assert reponse.status_code == 200
    assert len(requetes_select) == 1, f"{len(requetes_select)} requetes SELECT au lieu d'1 : {requetes_select}"


def test_fichier_introuvable_404(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/file")

    assert reponse.status_code == 404


def test_couverture_servie_sans_authentification(client, article, db_session, tmp_path):
    article.magazine.cover_thumbnail_path = str(tmp_path / f"{article.magazine_id}.webp")
    db_session.commit()
    (tmp_path / f"{article.magazine_id}.webp").write_bytes(b"RIFF....WEBP")

    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/cover")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "image/webp"


def test_couverture_absente_404(client, article):
    token = client.post(f"/api/articles/{article.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/{token}/cover")

    assert reponse.status_code == 404
