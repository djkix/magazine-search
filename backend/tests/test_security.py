"""Tests des primitives d'authentification.

Calcul pur : aucune base, aucun réseau. Couvre le durcissement apporté aux
jetons (algorithme figé, claims complétés) et l'invalidation de session au
changement de mot de passe.
"""

import jwt
import pytest

from app.config import get_settings
from app.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    password_fingerprint,
    verify_password,
)

settings = get_settings()


# ---- Hachage ----


def test_hachage_et_verification():
    empreinte = hash_password("un-mot-de-passe-solide")

    assert empreinte != "un-mot-de-passe-solide"
    assert verify_password("un-mot-de-passe-solide", empreinte)
    assert not verify_password("mauvais", empreinte)


def test_deux_hachages_du_meme_mot_de_passe_different():
    """Argon2 sale chaque hachage : deux appels ne doivent jamais coïncider."""
    assert hash_password("identique") != hash_password("identique")


# ---- Jetons ----


def test_aller_retour_du_jeton():
    jeton = create_access_token(subject="a@exemple.fr", password_hash="hash-quelconque")
    charge = decode_access_token(jeton)

    assert charge is not None
    assert charge["sub"] == "a@exemple.fr"


def test_claims_obligatoires_presents():
    charge = decode_access_token(
        create_access_token(subject="a@exemple.fr", password_hash="hash-quelconque")
    )

    for claim in ("sub", "exp", "iat", "jti", "pwf"):
        assert claim in charge, f"claim manquant : {claim}"


def test_jti_unique_entre_deux_jetons():
    """Sans jti, deux connexions dans la même seconde produisent des jetons
    identiques, et aucune révocation ciblée n'est possible plus tard."""
    a = decode_access_token(create_access_token("a@exemple.fr", "hash"))
    b = decode_access_token(create_access_token("a@exemple.fr", "hash"))

    assert a["jti"] != b["jti"]


def test_algorithme_fige_en_hs256():
    jeton = create_access_token("a@exemple.fr", "hash")

    assert JWT_ALGORITHM == "HS256"
    assert jwt.get_unverified_header(jeton)["alg"] == "HS256"


def test_jeton_signe_avec_un_autre_secret_rejete():
    usurpe = jwt.encode(
        {"sub": "a@exemple.fr", "exp": 9999999999}, "mauvais-secret", algorithm="HS256"
    )

    assert decode_access_token(usurpe) is None


def test_jeton_sans_sub_rejete():
    """`sub` et `exp` sont exigés au décodage : un jeton amputé de l'un des
    deux ne doit pas être accepté, même correctement signé."""
    ampute = jwt.encode({"exp": 9999999999}, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)

    assert decode_access_token(ampute) is None


def test_jeton_expire_rejete():
    perime = jwt.encode(
        {"sub": "a@exemple.fr", "exp": 1000000000},  # 2001
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(perime) is None


@pytest.mark.parametrize("valeur", ["", "pas-un-jeton", "a.b.c"])
def test_entrees_invalides_rejetees_sans_exception(valeur):
    assert decode_access_token(valeur) is None


# ---- Invalidation au changement de mot de passe ----


def test_empreinte_change_avec_le_hash():
    assert password_fingerprint("hash-a") != password_fingerprint("hash-b")


def test_empreinte_stable_pour_un_meme_hash():
    assert password_fingerprint("hash-a") == password_fingerprint("hash-a")


def test_changement_de_mot_de_passe_invalide_le_jeton():
    """C'est le mécanisme qui fait qu'un changement de mot de passe déconnecte
    les sessions ouvertes : le claim pwf ne correspond plus au hash en base."""
    ancien = hash_password("ancien-mot-de-passe")
    jeton = create_access_token("a@exemple.fr", ancien)

    nouveau = hash_password("nouveau-mot-de-passe")
    charge = decode_access_token(jeton)

    assert charge["pwf"] == password_fingerprint(ancien)
    assert charge["pwf"] != password_fingerprint(nouveau)
