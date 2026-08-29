import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, Theme
from app.services.gemini_quota import GeminiQuotaExceeded, consume_gemini_quota, mark_quota_exhausted_for_today
from app.services.toc import get_gemini_model

logger = logging.getLogger("app.magazine_themes")

MAX_THEMES_PER_MAGAZINE = 3

PROMPT = """Tu reçois le sommaire (liste des titres d'articles) d'un numéro \
de magazine français. Identifie entre 1 et {max_themes} thématiques \
pertinentes qui résument le contenu de ce numéro (par exemple \
"Automobile", "Bricolage", "Santé"...).

Voici les thématiques déjà utilisées ailleurs dans la bibliothèque : \
réutilise-en une si elle convient, plutôt que d'en créer une nouvelle \
proche d'une existante (par exemple ne crée pas "Voitures" si \
"Automobile" existe déjà et convient).

Thématiques existantes :
{vocabulary}

Sommaire de ce numéro :
{listing}"""

THEME_NAMES_SCHEMA = {"type": "array", "items": {"type": "string"}}


def generate_magazine_themes(db: Session, articles: list[Article]) -> list[str]:
    """Ask Gemini for a small set of theme names summarizing a single
    magazine's content, reusing the library's existing theme vocabulary
    when a match fits. Returns raw theme name strings - resolving them to
    `Theme` rows (get-or-create) is the caller's job."""
    settings = get_settings()
    if not settings.gemini_api_key or not articles:
        return []

    existing_names = [name for (name,) in db.query(Theme.name).order_by(Theme.name).all()]
    vocabulary = "\n".join(f"- {name}" for name in existing_names) if existing_names else "(aucune pour le moment)"
    listing = "\n".join(f"- {a.title}" for a in articles)

    prompt = PROMPT.format(max_themes=MAX_THEMES_PER_MAGAZINE, vocabulary=vocabulary, listing=listing)

    model = get_gemini_model(db)
    try:
        consume_gemini_quota(db, model)
    except GeminiQuotaExceeded as exc:
        logger.info("Skipping theme generation: %s", exc)
        return []

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=THEME_NAMES_SCHEMA,
            ),
        )
    except Exception as exc:
        if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
            mark_quota_exhausted_for_today(model)
        logger.error("Gemini theme generation request failed: %s", exc)
        return []

    try:
        data = json.loads(response.text or "[]")
    except json.JSONDecodeError:
        logger.error("Gemini returned non-JSON theme list: %r", (response.text or "")[:500])
        return []

    if not isinstance(data, list):
        return []

    names = []
    for item in data[:MAX_THEMES_PER_MAGAZINE]:
        name = str(item).strip()
        if name:
            names.append(name)
    return names
