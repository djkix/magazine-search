"""Limitation des tentatives de connexion.

Deux protections indépendantes :

- par adresse IP (slowapi), l'adresse étant lue à DROITE de X-Forwarded-For :
  un en-tête forgé par le client ne doit plus permettre de changer de
  compteur à chaque requête ;
- par compte (email visé), quelle que soit l'adresse d'origine.

Ni Redis ni PostgreSQL : compteurs slowapi en mémoire (RATE_LIMIT_STORAGE_URI
posé par conftest.py), verrou sur FauxRedis, base SQLite en mémoire.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.rate_limit import adresse_client, limiter
from app.security import hash_password
from app.services.verrouillage_login import VerrouillageCompte, get_verrouillage
from tests.faux_redis import FauxRedis, Horloge

EMAIL = "lecteur@exemple.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide"


def _requete(entetes: list[tuple[str, str]], pair: str = "172.18.0.5") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/login",
            "headers": [(k.lower().encode(), v.encode()) for k, v in entetes],
            "client": (pair, 40000),
        }
    )


# ---- adresse_client ----


def test_entree_ajoutee_par_npm_retenue_malgre_un_en_tete_forge():
    """NPM ajoute l'IP réelle APRÈS la valeur forgée : c'est elle qui compte."""
    requete = _requete([("X-Forwarded-For", "6.6.6.6, 203.0.113.9")])

    assert adresse_client(requete, 1) == "203.0.113.9"


def test_en_tetes_multiples_concatenes_dans_l_ordre():
    requete = _requete([("X-Forwarded-For", "6.6.6.6"), ("X-Forwarded-For", "203.0.113.9")])

    assert adresse_client(requete, 1) == "203.0.113.9"


def test_deux_proxys_de_confiance():
    requete = _requete([("X-Forwarded-For", "6.6.6.6, 203.0.113.9, 198.51.100.1")])

    assert adresse_client(requete, 2) == "203.0.113.9"


def test_moins_d_entrees_que_de_sauts_retient_la_plus_a_gauche():
    requete = _requete([("X-Forwarded-For", "203.0.113.9")])

    assert adresse_client(requete, 2) == "203.0.113.9"


def test_sans_en_tete_repli_sur_le_pair():
    assert adresse_client(_requete([]), 1) == "172.18.0.5"


def test_zero_saut_ignore_l_en_tete():
    requete = _requete([("X-Forwarded-For", "6.6.6.6")])

    assert adresse_client(requete, 0) == "172.18.0.5"


def test_ecritures_differentes_d_une_meme_ipv6_meme_cle():
    a = _requete([("X-Forwarded-For", "2001:DB8::0001")])
    b = _requete([("X-Forwarded-For", "2001:db8::1")])

    assert adresse_client(a, 1) == adresse_client(b, 1)


# ---- bout en bout sur /api/login ----


@pytest.fixture
def horloge():
    return Horloge()


@pytest.fixture
def client(horloge):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        User(email=EMAIL, password_hash=hash_password(MOT_DE_PASSE), display_name="Lecteur", is_active=True)
    )
    session.commit()

    verrou = VerrouillageCompte(FauxRedis(horloge), max_echecs=3, fenetre_secondes=900, duree_verrou_secondes=900)

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_verrouillage] = lambda: verrou
    limiter.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        limiter.reset()
        session.close()


def _connexion(client, ip_vue_par_npm, mot_de_passe="faux", prefixe_forge=None, email=EMAIL):
    xff = f"{prefixe_forge}, {ip_vue_par_npm}" if prefixe_forge else ip_vue_par_npm
    return client.post(
        "/api/login",
        json={"email": email, "password": mot_de_passe},
        headers={"X-Forwarded-For": xff},
    )


def test_en_tete_forge_ne_reinitialise_plus_le_compteur_ip(client):
    """Avant correctif : chaque valeur forgée ouvrait un nouveau compteur."""
    codes = [
        _connexion(client, "203.0.113.9", prefixe_forge=f"10.0.0.{i}", email=f"inconnu{i}@exemple.fr").status_code
        for i in range(6)
    ]

    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_deux_clients_reels_ont_des_compteurs_distincts(client):
    for i in range(5):
        _connexion(client, "203.0.113.9", email=f"inconnu{i}@exemple.fr")

    assert _connexion(client, "203.0.113.9", email="autre@exemple.fr").status_code == 429
    assert _connexion(client, "198.51.100.7", email="autre@exemple.fr").status_code == 401


def test_compte_verrouille_malgre_des_ip_differentes(client):
    for i in range(3):
        assert _connexion(client, f"198.51.100.{i}").status_code == 401

    # Bon mot de passe, nouvelle adresse : refusé tant que dure le verrou.
    reponse = _connexion(client, "198.51.100.50", mot_de_passe=MOT_DE_PASSE)
    assert reponse.status_code == 429
    assert int(reponse.headers["Retry-After"]) > 0


def test_verrou_leve_apres_expiration(client, horloge):
    for i in range(3):
        _connexion(client, f"198.51.100.{i}")

    horloge.maintenant += timedelta(minutes=16)

    assert _connexion(client, "198.51.100.60", mot_de_passe=MOT_DE_PASSE).status_code == 200


def test_email_inexistant_verrouille_aussi(client):
    """Sinon la présence ou l'absence de verrou révélerait les comptes existants."""
    for i in range(3):
        _connexion(client, f"198.51.100.{i}", email="personne@exemple.fr")

    assert _connexion(client, "198.51.100.70", email="personne@exemple.fr").status_code == 429


def test_succes_remet_le_compteur_a_zero(client):
    for i in range(2):
        _connexion(client, f"198.51.100.{i}")
    assert _connexion(client, "198.51.100.80", mot_de_passe=MOT_DE_PASSE).status_code == 200

    for i in range(2):
        assert _connexion(client, f"198.51.100.{10 + i}").status_code == 401
    assert _connexion(client, "198.51.100.90", mot_de_passe=MOT_DE_PASSE).status_code == 200


def test_verrou_insensible_a_la_casse(client):
    for i in range(3):
        _connexion(client, f"198.51.100.{i}", email=EMAIL.upper())

    assert _connexion(client, "198.51.100.99", mot_de_passe=MOT_DE_PASSE).status_code == 429


def test_google_soumis_a_la_meme_limite_ip(client, monkeypatch):
    """/auth/google partage la clé client : un en-tête forgé n'y aide pas non plus."""
    from app.services import google_auth

    def _refus(credential, request, audience):
        raise ValueError("jeton invalide")

    monkeypatch.setattr(google_auth.google_id_token, "verify_oauth2_token", _refus)
    codes = [
        client.post(
            "/api/auth/google",
            json={"credential": "x"},
            headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
        ).status_code
        for i in range(6)
    ]

    assert codes[:5] == [401] * 5
    assert codes[5] == 429
