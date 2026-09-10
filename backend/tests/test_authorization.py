"""Frontière d'autorisation entre comptes standard et comptes administrateur.

Ces tests deviennent essentiels dès lors que l'instance accueille des comptes
tiers : ils vérifient qu'AUCUNE route `/api/admin` n'est accessible à un
utilisateur non administrateur.

Le contrôle est **générique** : il parcourt les routes réellement déclarées
par l'application. Une nouvelle route d'administration ajoutée plus tard est
donc couverte automatiquement, sans qu'il faille penser à compléter une liste.

Aucune infrastructure n'est requise : l'autorisation est refusée avant que le
corps de l'endpoint ne s'exécute, donc ni PostgreSQL ni Redis ne sont
sollicités. Les dépendances sont neutralisées par `dependency_overrides`.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.deps import get_current_user
from app.main import app
from app.models import User

PREFIXE_ADMIN = "/api/admin"
METHODES_IGNOREES = {"HEAD", "OPTIONS"}


def _utilisateur(is_admin: bool) -> User:
    """Instance de modèle non persistée : suffit aux dépendances d'auth."""
    u = User()
    u.id = 1
    u.email = "utilisateur@exemple.fr"
    u.display_name = "Utilisateur"
    u.is_admin = is_admin
    u.is_active = True
    u.password_hash = "hash-non-utilise-ici"
    return u


def _sans_base():
    """Neutralise l'accès base : aucun test ici ne doit l'atteindre."""
    yield None


def _routes_admin():
    """(méthode, chemin) de chaque route d'administration déclarée."""
    trouvees = []
    for route in app.routes:
        chemin = getattr(route, "path", "")
        if not chemin.startswith(PREFIXE_ADMIN):
            continue
        for methode in getattr(route, "methods", set()) - METHODES_IGNOREES:
            # Les paramètres de chemin sont remplacés par une valeur factice :
            # on teste le refus d'accès, jamais la ressource elle-même.
            trouvees.append((methode, re.sub(r"\{[^}]+\}", "1", chemin)))
    return sorted(set(trouvees))


ROUTES_ADMIN = _routes_admin()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _sans_base
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_des_routes_admin_existent():
    """Garde-fou : si cette liste devenait vide, les tests ci-dessous
    passeraient sans rien vérifier du tout."""
    assert len(ROUTES_ADMIN) >= 10, f"Trop peu de routes détectées : {ROUTES_ADMIN}"


@pytest.mark.parametrize(("methode", "chemin"), ROUTES_ADMIN)
def test_utilisateur_standard_refuse_sur_toute_route_admin(client, methode, chemin):
    app.dependency_overrides[get_current_user] = lambda: _utilisateur(is_admin=False)

    reponse = client.request(methode, chemin)

    assert reponse.status_code == 403, (
        f"{methode} {chemin} a répondu {reponse.status_code} au lieu de 403 "
        "pour un utilisateur non administrateur"
    )


@pytest.mark.parametrize(("methode", "chemin"), ROUTES_ADMIN)
def test_visiteur_non_authentifie_refuse(client, methode, chemin):
    """Sans jeton ni cookie : 401, et surtout jamais 200."""
    reponse = client.request(methode, chemin)

    assert reponse.status_code == 401, (
        f"{methode} {chemin} a répondu {reponse.status_code} au lieu de 401 "
        "pour un visiteur non authentifié"
    )


def test_administrateur_franchit_la_frontiere(client):
    """Contrôle inverse : la garde ne doit pas bloquer un administrateur.

    Sans cette vérification, une garde qui refuserait tout le monde ferait
    passer les deux tests précédents.
    """
    app.dependency_overrides[get_current_user] = lambda: _utilisateur(is_admin=True)

    reponse = client.get(f"{PREFIXE_ADMIN}/magazines/1/progress")

    # La base étant neutralisée, l'endpoint peut échouer ensuite — seul
    # compte le fait que l'autorisation, elle, ait été accordée.
    assert reponse.status_code != 403
