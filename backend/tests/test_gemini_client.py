"""Traduction des erreurs du SDK Gemini en pauses compréhensibles."""

from datetime import datetime, timedelta, timezone

from google.genai import errors

from app.services.gemini_client import traduire_erreur
from app.services.gemini_quota import (
    CLE_INVALIDE,
    ERREUR_API,
    MODELE_INTROUVABLE,
    QUOTA_JOUR,
    QUOTA_MINUTE,
)

MAINTENANT = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _erreur(code, status, message, details=None):
    corps = {"error": {"code": code, "message": message, "status": status}}
    if details:
        corps["error"]["details"] = details
    return errors.ClientError(code, corps)


def test_429_par_jour_donne_un_quota_journalier():
    exc = _erreur(
        429, "RESOURCE_EXHAUSTED",
        "Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel-FreeTier",
    )
    erreur = traduire_erreur(exc, MAINTENANT)
    assert erreur.raison == QUOTA_JOUR


def test_429_par_minute_reprend_au_delai_indique_par_google():
    exc = _erreur(
        429, "RESOURCE_EXHAUSTED",
        "Quota exceeded for metric GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
        details=[{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "34s"}],
    )
    erreur = traduire_erreur(exc, MAINTENANT)
    assert erreur.raison == QUOTA_MINUTE
    assert MAINTENANT + timedelta(seconds=34) <= erreur.jusqua <= MAINTENANT + timedelta(seconds=40)


def test_429_par_minute_sans_delai_n_invente_pas_d_heure():
    erreur = traduire_erreur(_erreur(429, "RESOURCE_EXHAUSTED", "trop vite"), MAINTENANT)
    assert erreur.raison == QUOTA_MINUTE
    assert erreur.jusqua is None


def test_404_est_un_modele_introuvable():
    erreur = traduire_erreur(_erreur(404, "NOT_FOUND", "models/x is not found"), MAINTENANT)
    assert erreur.raison == MODELE_INTROUVABLE


def test_cle_refusee_est_une_cle_invalide():
    assert traduire_erreur(_erreur(403, "PERMISSION_DENIED", "denied"), MAINTENANT).raison == CLE_INVALIDE
    assert traduire_erreur(_erreur(401, "UNAUTHENTICATED", "no"), MAINTENANT).raison == CLE_INVALIDE
    erreur_400 = _erreur(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.")
    assert traduire_erreur(erreur_400, MAINTENANT).raison == CLE_INVALIDE


def test_toute_autre_erreur_est_une_erreur_d_api():
    assert traduire_erreur(_erreur(500, "INTERNAL", "boom"), MAINTENANT).raison == ERREUR_API
    assert traduire_erreur(RuntimeError("réseau coupé"), MAINTENANT).raison == ERREUR_API
