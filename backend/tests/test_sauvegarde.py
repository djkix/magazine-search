"""Sauvegarde vers le NAS vue du tableau de bord : alerte et « Sauvegarder maintenant ».

Le refus pour un non-administrateur est couvert par test_authorization.py,
qui parcourt toutes les routes /api/admin.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.deps import get_current_admin
from app.main import app
from app.models import BackupRequest, BackupRun, User
from app.services.sauvegarde import alerte

MAINTENANT = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def il_y_a(heures: float) -> datetime:
    return MAINTENANT - timedelta(hours=heures)


def test_alerte_sans_tentative():
    assert alerte(None, "", None, MAINTENANT) is None


def test_alerte_reussie_recente():
    assert alerte(True, "", il_y_a(10), MAINTENANT) is None


def test_alerte_derniere_en_echec():
    assert alerte(False, "étape base (code 1)", il_y_a(20), MAINTENANT) == (
        "Dernière sauvegarde en échec : étape base (code 1)."
    )


def test_alerte_rien_depuis_36_h_date_naive():
    assert alerte(True, "", il_y_a(37).replace(tzinfo=None), MAINTENANT) == (
        "Aucune sauvegarde réussie depuis 36 h."
    )


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
def client(db_session):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_admin] = lambda: User(id=1, email="admin@exemple.fr", is_admin=True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _tentative(heures: float, reussie: bool, message: str = "") -> BackupRun:
    fin = datetime.now(timezone.utc) - timedelta(hours=heures)
    return BackupRun(started_at=fin, finished_at=fin, succeeded=reussie, message=message)


def test_etat_sans_tentative(client):
    assert client.get("/api/admin/backup").json() == {
        "derniere_reussite": None,
        "derniere_tentative": None,
        "demandee": False,
        "alerte": None,
    }


def test_etat_derniere_en_echec(client, db_session):
    db_session.add_all([_tentative(5, True), _tentative(1, False, "étape donnees (code 23)")])
    db_session.commit()

    etat = client.get("/api/admin/backup").json()

    assert etat["derniere_reussite"] is not None
    assert etat["derniere_tentative"]["reussie"] is False
    assert etat["alerte"] == "Dernière sauvegarde en échec : étape donnees (code 23)."


def test_deux_demandes_n_en_font_qu_une(client, db_session):
    assert client.post("/api/admin/backup/request").status_code == 204
    assert client.post("/api/admin/backup/request").status_code == 204

    assert db_session.query(BackupRequest).count() == 1
    assert client.get("/api/admin/backup").json()["demandee"] is True
