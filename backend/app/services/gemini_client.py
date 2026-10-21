"""Appel à l'API Gemini, et traduction de ses erreurs en raisons de pause."""

import re
from datetime import datetime, timedelta, timezone

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.gemini_quota import (
    CLE_INVALIDE,
    ERREUR_API,
    MODELE_INTROUVABLE,
    QUOTA_JOUR,
    QUOTA_MINUTE,
    ErreurGemini,
)

_DELAI_RE = re.compile(r"retryDelay\W+(\d+(?:\.\d+)?)s")


def traduire_erreur(exc: Exception, maintenant: datetime | None = None) -> ErreurGemini:
    """Convertit une exception du SDK en ErreurGemini.

    Pour un quota par minute, l'heure de reprise est celle que Google indique
    (`retryDelay`), à une seconde près ; absente, elle reste à None.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    code = getattr(exc, "code", None)
    texte = str(exc)

    if code == 429:
        if "PerDay" in texte:
            return ErreurGemini(QUOTA_JOUR, "Quota journalier Gemini atteint.")
        correspondance = _DELAI_RE.search(texte)
        jusqua = None
        if correspondance:
            jusqua = maintenant + timedelta(seconds=float(correspondance.group(1)) + 1)
        return ErreurGemini(QUOTA_MINUTE, "Limite par minute de Gemini atteinte.", jusqua)
    if code == 404:
        return ErreurGemini(MODELE_INTROUVABLE, "Modèle Gemini introuvable.")
    if code in (401, 403) or (code == 400 and "API key" in texte):
        return ErreurGemini(CLE_INVALIDE, "Clé API Gemini refusée.")
    return ErreurGemini(ERREUR_API, f"Erreur Gemini : {texte[:200]}")


def appeler_gemini(prompt: str) -> tuple[str, int]:
    """Envoie la requête et rend (texte JSON, tokens utilisés).

    Aucune nouvelle tentative automatique : un échec devient une ErreurGemini,
    et la pause qui en découle décide de la reprise.
    """
    # Import différé : classification_gemini importe ce module.
    from app.services.classification_gemini import SCHEMA_REPONSE

    settings = get_settings()
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
    )
    try:
        reponse = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=SCHEMA_REPONSE,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - toute panne devient une pause
        raise traduire_erreur(exc) from exc

    usage = reponse.usage_metadata
    tokens = (usage.total_token_count if usage else None) or 0
    return reponse.text or "", tokens
