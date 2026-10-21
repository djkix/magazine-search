"""Endpoint d'état de la classification Gemini, affiché sur le tableau de bord."""

from datetime import datetime, timedelta, timezone

import pytest
from faux_redis import FauxRedis, Horloge
from fastapi.testclient import TestClient

from app.database import get_db
from app.deps import get_current_admin
from app.main import app
from app.models import User
from app.routers import admin
from app.services.gemini_quota import QUOTA_JOUR, SuiviQuota


@pytest.fixture
def client(db_taxonomie, monkeypatch):
    redis = FauxRedis(Horloge(datetime.now(timezone.utc)))
    monkeypatch.setattr(admin, "redis_conn", redis)
    monkeypatch.setattr(admin.settings, "gemini_api_key", "cle-de-test")
    monkeypatch.setattr(admin.settings, "gemini_model", "gemini-3.8-flash")

    def _admin():
        u = User()
        u.id = 1
        u.email = "admin@exemple.fr"
        u.display_name = "Admin"
        u.is_admin = True
        u.is_active = True
        u.password_hash = "x"
        return u

    def _get_db():
        yield db_taxonomie

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_admin] = _admin
    yield TestClient(app), redis
    app.dependency_overrides.clear()


def test_inactif_sans_cle_api(client, monkeypatch):
    http, redis = client
    monkeypatch.setattr(admin.settings, "gemini_api_key", "")

    corps = http.get("/api/admin/classification").json()

    assert corps == {
        "actif": False,
        "modele": "gemini-3.8-flash",
        "en_attente": 0,
        "requetes_aujourdhui": 0,
        "limite_jour": 0,
        "pause": None,
    }


def test_actif_renvoie_attente_et_compteurs(client, db_taxonomie, fabrique):
    http, redis = client
    fabrique.article("Premier orphelin")
    fabrique.article("Deuxième orphelin")
    db_taxonomie.commit()
    suivi = SuiviQuota(redis, rpm=5, rpd=20, tpm=250_000)
    suivi.enregistrer(10)
    suivi.enregistrer(10)

    corps = http.get("/api/admin/classification").json()

    assert corps["actif"] is True
    assert corps["en_attente"] == 2
    assert corps["requetes_aujourdhui"] == 2
    assert corps["limite_jour"] == 18
    assert corps["pause"] is None


def test_renvoie_la_pause_en_cours(client):
    http, redis = client
    suivi = SuiviQuota(redis, rpm=5, rpd=20, tpm=250_000)
    jusqua = datetime.now(timezone.utc) + timedelta(hours=3)
    suivi.poser_pause(QUOTA_JOUR, jusqua)

    corps = http.get("/api/admin/classification").json()

    assert corps["pause"]["raison"] == QUOTA_JOUR
    assert datetime.fromisoformat(corps["pause"]["jusqua"]) == jusqua


def test_route_reservee_a_l_admin(client):
    http, _ = client
    from app.deps import get_current_user

    app.dependency_overrides.pop(get_current_admin)
    nonadmin = User()
    nonadmin.id, nonadmin.email, nonadmin.is_admin, nonadmin.is_active = 2, "u@x.fr", False, True
    nonadmin.display_name, nonadmin.password_hash = "U", "x"
    app.dependency_overrides[get_current_user] = lambda: nonadmin

    assert http.get("/api/admin/classification").status_code == 403
