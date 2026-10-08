"""Statistiques du tableau de bord admin.

Couvre uniquement le compteur de nouveaux comptes (7 derniers jours) ajouté
pour signaler les inscriptions via Google — le reste de /admin/stats
n'avait aucune couverture avant ce fichier, hors de son périmètre ici.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import get_current_admin
from app.main import app
from app.models import User


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

    def _admin():
        u = User()
        u.id = 1
        u.email = "admin@exemple.fr"
        u.display_name = "Admin"
        u.is_admin = True
        u.is_active = True
        u.password_hash = "hash-non-utilise-ici"
        return u

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_admin] = _admin
    yield TestClient(app)
    app.dependency_overrides.clear()


def _utilisateur(email: str, cree_il_y_a_jours: int) -> User:
    u = User(email=email, display_name=email, password_hash="x", is_admin=False, is_active=True)
    u.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=cree_il_y_a_jours)
    return u


def test_compte_les_comptes_crees_dans_les_7_derniers_jours(client, db_session):
    db_session.add_all(
        [
            _utilisateur("recent1@exemple.fr", 0),
            _utilisateur("recent2@exemple.fr", 6),
            _utilisateur("ancien@exemple.fr", 8),
        ]
    )
    db_session.commit()

    reponse = client.get("/api/admin/stats")

    assert reponse.status_code == 200
    assert reponse.json()["new_users_7j"] == 2
