"""Partage d'un numéro entier par lien public, sans compte.

Complément à test_partage.py (partage d'un article) : même mécanisme,
jeton distinct, appliqué à Magazine plutôt qu'à Article. Un numéro et l'un
de ses articles peuvent être partagés indépendamment, avec des liens
différents.
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
from app.models import Collection, Magazine, User


@pytest.fixture
def db_session():
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
def magazine(db_session):
    collection = Collection(name="Une collection")
    db_session.add(collection)
    db_session.commit()
    m = Magazine(
        title="Test",
        filename="test.pdf",
        file_path="test.pdf",
        file_hash="h1",
        file_size=1000,
        file_mtime=datetime.datetime.now(datetime.timezone.utc),
        collection_id=collection.id,
    )
    db_session.add(m)
    db_session.commit()
    return m


def test_creation_du_partage_genere_un_token(client, magazine):
    reponse = client.post(f"/api/magazines/{magazine.id}/share")

    assert reponse.status_code == 200
    assert len(reponse.json()["token"]) > 20


def test_deux_appels_renvoient_le_meme_token(client, magazine):
    premier = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    second = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]

    assert premier == second


def test_magazine_inconnu_404(client):
    reponse = client.post("/api/magazines/999999/share")

    assert reponse.status_code == 404


def test_metadonnees_token_inconnu_404(client):
    reponse = client.get("/api/partage/magazine/un-token-qui-n-existe-pas")

    assert reponse.status_code == 404


def test_metadonnees_token_valide(client, magazine):
    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]

    reponse = client.get(f"/api/partage/magazine/{token}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["magazine_title"] == "Test"
    assert corps["collection_name"] == "Une collection"


def test_metadonnees_accessible_sans_authentification(client, magazine):
    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/magazine/{token}")

    assert reponse.status_code == 200


def test_fichier_sert_le_pdf_par_plages(client, magazine, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "processed_dir", str(tmp_path))
    (tmp_path / f"{magazine.id}.pdf").write_bytes(b"%PDF-1.4\n" + b"A" * 991)

    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/magazine/{token}/file", headers={"Range": "bytes=0-9"})

    assert reponse.status_code == 206
    assert reponse.headers["accept-ranges"] == "bytes"
    assert reponse.content == b"%PDF-1.4\nA"


def test_fichier_introuvable_404(client, magazine):
    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/magazine/{token}/file")

    assert reponse.status_code == 404


def test_couverture_servie_sans_authentification(client, magazine, db_session, tmp_path):
    magazine.cover_thumbnail_path = str(tmp_path / f"{magazine.id}.webp")
    db_session.commit()
    (tmp_path / f"{magazine.id}.webp").write_bytes(b"RIFF....WEBP")

    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/magazine/{token}/cover")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "image/webp"


def test_couverture_absente_404(client, magazine):
    token = client.post(f"/api/magazines/{magazine.id}/share").json()["token"]
    app.dependency_overrides.pop(get_current_user, None)

    reponse = client.get(f"/api/partage/magazine/{token}/cover")

    assert reponse.status_code == 404
