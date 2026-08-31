import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, Magazine, Theme
from app.services.gemini_quota import consume_gemini_quota, mark_quota_exhausted_for_today
from app.services.toc import get_gemini_model

logger = logging.getLogger("app.theme_batch")

MAX_THEMES_PER_MAGAZINE = 3

BATCH_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "magazine_id": {"type": "integer"},
            "themes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["magazine_id", "themes"],
    },
}

PROMPT_HEADER = """Tu reçois le sommaire (liste des titres d'articles) de plusieurs \
numéros de magazines français, chacun délimité par une ligne "=== Magazine <id> ===".

Pour chaque numéro, identifie entre 1 et {max_themes} thématiques qui résument \
son contenu (par exemple "Automobile", "Bricolage", "Santé"...), en réutilisant \
si possible une thématique de la liste ci-dessous plutôt que d'en créer une \
nouvelle proche d'une existante (par exemple ne crée pas "Voitures" si \
"Automobile" existe déjà et convient) - l'objectif est de regrouper des \
numéros similaires sous les mêmes thématiques plutôt que d'en multiplier des \
proches.

Thématiques déjà utilisées ailleurs dans la bibliothèque :
{vocabulary}

Réponds avec exactement un élément par numéro ci-dessous, dans n'importe \
quel ordre, en reprenant son magazine_id exact.

"""


def assign_themes_batch(db: Session, magazines_with_articles: list[tuple[Magazine, list[Article]]]) -> dict[int, list[str]]:
    """Clusters several magazines' already-extracted sommaires into shared
    themes in a SINGLE Gemini request, instead of one request per magazine.
    Sommaire/article extraction itself is done locally from OCR text (see
    sommaire_ocr.py) with no Gemini call at all - this is Gemini's only
    remaining role in the ingestion pipeline, and the only place request
    quota is spent.

    Returns {magazine_id: [theme_name, ...]}. Raises on a whole-batch
    failure (missing API key, quota exhausted, malformed response) - the
    caller just leaves every magazine in the batch without themes and lets
    the next batch run pick them up again, since there's no per-magazine
    status to mark failed here.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY non configurée")

    sections = []
    any_articles = False
    for magazine, articles in magazines_with_articles:
        if articles:
            any_articles = True
        listing = "\n".join(f"- {a.title}" for a in articles) or "(aucun article identifié)"
        sections.append(f"=== Magazine {magazine.id} ===\n{listing}")

    if not any_articles:
        raise RuntimeError("Aucun sommaire disponible pour ce lot")

    existing_names = [name for (name,) in db.query(Theme.name).order_by(Theme.name).all()]
    vocabulary = "\n".join(f"- {name}" for name in existing_names) if existing_names else "(aucune pour le moment)"
    prompt = PROMPT_HEADER.format(max_themes=MAX_THEMES_PER_MAGAZINE, vocabulary=vocabulary) + "\n\n".join(sections)

    model = get_gemini_model(db)
    consume_gemini_quota(db, model)  # one unit for the whole batch, however many magazines it covers

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=BATCH_SCHEMA,
            ),
        )
    except Exception as exc:
        if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
            mark_quota_exhausted_for_today(model)
            raise RuntimeError("Quota Gemini dépassé (429) — réessayez plus tard.") from exc
        raise

    try:
        data = json.loads(response.text or "[]")
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON theme batch response: %r", (response.text or "")[:500])
        raise RuntimeError("Réponse Gemini invalide (JSON illisible)") from exc

    if not isinstance(data, list):
        raise RuntimeError("Réponse Gemini invalide (format inattendu)")

    results: dict[int, list[str]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        magazine_id = item.get("magazine_id")
        if not isinstance(magazine_id, int):
            continue
        themes = [str(t).strip() for t in (item.get("themes") or []) if str(t).strip()][:MAX_THEMES_PER_MAGAZINE]
        results[magazine_id] = themes

    return results
