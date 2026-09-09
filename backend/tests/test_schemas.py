"""Tests des garde-fous de validation ajoutés sur les schémas Pydantic.

Calcul pur : aucune base, aucun réseau. Ces règles ont été ajoutées lors du
durcissement de sécurité — sans test, rien ne signalerait leur disparition
lors d'un futur refactor.
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    MDP_LONGUEUR_MIN,
    ArticleCreate,
    ArticleUpdate,
    CollectionTagsUpdate,
    LoginRequest,
    PasswordReset,
    UserCreate,
)


# ---- Politique de mot de passe ----


def test_creation_utilisateur_refuse_un_mot_de_passe_trop_court():
    with pytest.raises(ValidationError):
        UserCreate(
            email="a@exemple.fr",
            display_name="Test",
            password="court",
        )


def test_creation_utilisateur_refuse_un_mot_de_passe_vide():
    with pytest.raises(ValidationError):
        UserCreate(email="a@exemple.fr", display_name="Test", password="")


def test_creation_utilisateur_accepte_un_mot_de_passe_conforme():
    u = UserCreate(
        email="a@exemple.fr",
        display_name="Test",
        password="x" * MDP_LONGUEUR_MIN,
    )
    assert u.is_admin is False


def test_reinitialisation_soumise_a_la_meme_longueur_minimale():
    with pytest.raises(ValidationError):
        PasswordReset(new_password="x" * (MDP_LONGUEUR_MIN - 1))

    PasswordReset(new_password="x" * MDP_LONGUEUR_MIN)


def test_connexion_non_soumise_a_la_politique():
    """Choix délibéré : appliquer la règle à la connexion renverrait 422 au
    lieu de 401 pour un mot de passe court, ce qui divulguerait la politique
    et empêcherait un compte ancien de se connecter pour la changer."""
    LoginRequest(email="a@exemple.fr", password="court")


# ---- Bornes sur les pages d'article ----


def test_page_de_debut_doit_etre_positive():
    with pytest.raises(ValidationError):
        ArticleCreate(title="Titre", start_page=0)


def test_page_de_fin_ne_peut_preceder_la_page_de_debut():
    with pytest.raises(ValidationError):
        ArticleCreate(title="Titre", start_page=10, end_page=5)


def test_plage_de_pages_valide_acceptee():
    a = ArticleCreate(title="Titre", start_page=10, end_page=12)
    assert (a.start_page, a.end_page) == (10, 12)

    ArticleCreate(title="Titre", start_page=10, end_page=10)
    ArticleCreate(title="Titre", start_page=10)  # page de fin facultative


def test_mise_a_jour_partielle_ne_declenche_pas_le_controle_dordre():
    """Les deux bornes étant facultatives à la mise à jour, le contrôle ne
    doit s'appliquer que lorsque les deux sont fournies."""
    ArticleUpdate(end_page=5)
    ArticleUpdate(start_page=10)

    with pytest.raises(ValidationError):
        ArticleUpdate(start_page=10, end_page=5)


def test_titre_darticle_non_vide():
    with pytest.raises(ValidationError):
        ArticleCreate(title="", start_page=1)


# ---- Cardinalité des tags ----


def test_liste_de_tags_bornee():
    CollectionTagsUpdate(tag_ids=list(range(200)))

    with pytest.raises(ValidationError):
        CollectionTagsUpdate(tag_ids=list(range(201)))


def test_liste_de_tags_vide_autorisee():
    assert CollectionTagsUpdate().tag_ids == []
