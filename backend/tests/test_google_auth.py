"""Connexion "Se connecter avec Google".

Aucun appel réseau réel : `verify_oauth2_token` est systématiquement
remplacé par un faux qui renvoie des claims construites à la main, ou lève
l'exception que la bibliothèque Google lèverait pour un jeton invalide.

Couvre le point le plus sensible de cette fonctionnalité : le rattachement
par EMAIL (pas par google_sub), qui garantit qu'un compte créé à la main par
un administrateur et un login Google ultérieur avec le même email
fusionnent sur la même ligne au lieu de créer un doublon.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User
from app.security import verify_password
from app.services import google_auth
from app.services.google_auth import GoogleAuthInvalide, authentifier_ou_creer, verifier_id_token

CLAIMS_VALIDES = {
    "email": "utilisateur@exemple.fr",
    "email_verified": True,
    "sub": "1234567890",
    "name": "Utilisateur Exemple",
}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _mock_verify(monkeypatch, retour=None, exception=None):
    def _faux(credential, request, audience):
        if exception is not None:
            raise exception
        return retour

    monkeypatch.setattr(google_auth.google_id_token, "verify_oauth2_token", _faux)


# ---- verifier_id_token ----


def test_jeton_valide_renvoie_les_claims(monkeypatch):
    _mock_verify(monkeypatch, retour=CLAIMS_VALIDES)

    assert verifier_id_token("un-jeton") == CLAIMS_VALIDES


def test_value_error_traduite_en_google_auth_invalide(monkeypatch):
    """verify_oauth2_token lève ValueError pour toute défaillance (jeton
    expiré, signature invalide, mauvaise audience...) — on ne fait que la
    traduire dans notre propre exception, sans réinventer sa logique."""
    _mock_verify(monkeypatch, exception=ValueError("jeton expiré"))

    with pytest.raises(GoogleAuthInvalide):
        verifier_id_token("un-jeton")


# ---- authentifier_ou_creer ----


def test_email_non_verifie_rejete_sans_toucher_la_base(monkeypatch, db):
    claims = {**CLAIMS_VALIDES, "email_verified": False}
    _mock_verify(monkeypatch, retour=claims)

    with pytest.raises(GoogleAuthInvalide):
        authentifier_ou_creer(db, "un-jeton")

    assert db.query(User).count() == 0


def test_creation_d_un_nouveau_compte(monkeypatch, db):
    _mock_verify(monkeypatch, retour=CLAIMS_VALIDES)

    user = authentifier_ou_creer(db, "un-jeton")

    assert user.email == CLAIMS_VALIDES["email"]
    assert user.google_sub == CLAIMS_VALIDES["sub"]
    assert user.is_admin is False
    assert user.is_active is True
    assert user.password_hash
    # Le mot de passe aléatoire ne doit correspondre à rien de connu : il est
    # généré puis immédiatement jeté, jamais révélé.
    assert not verify_password("", user.password_hash)
    assert not verify_password(CLAIMS_VALIDES["sub"], user.password_hash)


def test_compte_existant_fusionne_par_email(monkeypatch, db):
    """Un compte créé à la main par mot de passe, avec le même email qu'un
    login Google ultérieur, doit devenir la MÊME ligne — pas un doublon."""
    compte_existant = User(
        email=CLAIMS_VALIDES["email"],
        display_name="Déjà là",
        password_hash="hash-du-mot-de-passe-choisi-par-l-administrateur",
        google_sub=None,
        is_admin=False,
        is_active=True,
    )
    db.add(compte_existant)
    db.commit()
    id_initial = compte_existant.id

    _mock_verify(monkeypatch, retour=CLAIMS_VALIDES)
    user = authentifier_ou_creer(db, "un-jeton")

    assert db.query(User).count() == 1
    assert user.id == id_initial
    assert user.google_sub == CLAIMS_VALIDES["sub"]
    # Le mot de passe existant n'est pas écrasé par un login Google.
    assert user.password_hash == "hash-du-mot-de-passe-choisi-par-l-administrateur"


def test_compte_desactive_rejete(monkeypatch, db):
    """Une désactivation par l'administrateur reste la plus forte autorité :
    Google ne doit pas pouvoir la contourner."""
    compte_desactive = User(
        email=CLAIMS_VALIDES["email"],
        display_name="Désactivé",
        password_hash="hash-quelconque",
        google_sub=None,
        is_admin=False,
        is_active=False,
    )
    db.add(compte_desactive)
    db.commit()

    _mock_verify(monkeypatch, retour=CLAIMS_VALIDES)

    with pytest.raises(GoogleAuthInvalide):
        authentifier_ou_creer(db, "un-jeton")
