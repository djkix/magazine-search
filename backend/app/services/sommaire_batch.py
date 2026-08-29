import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Magazine, Page, Theme
from app.services.gemini_quota import consume_gemini_quota, mark_quota_exhausted_for_today
from app.services.toc import MAX_SOMMAIRE_PAGE, get_gemini_model

logger = logging.getLogger("app.sommaire_batch")

MAX_THEMES_PER_MAGAZINE = 3

BATCH_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "magazine_id": {"type": "integer"},
            "articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "page": {"type": "integer"},
                    },
                    "required": ["title", "page"],
                },
            },
            "themes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["magazine_id", "articles", "themes"],
    },
}

PROMPT_HEADER = """Tu reçois le texte OCR des premières pages de plusieurs numéros de \
magazines français, chacun délimité par une ligne "=== Magazine <id> ===".

Pour chaque numéro, indépendamment des autres :
1. Repère son "sommaire" (table des matières), qui liste les articles avec \
leur page de début, souvent sous la forme "Titre de l'article ..... 12". \
Extrait uniquement les articles listés dans ce sommaire ; si aucun sommaire \
n'est identifiable dans son texte, renvoie une liste d'articles vide pour ce \
numéro.
2. Identifie entre 1 et {max_themes} thématiques qui résument son contenu \
(par exemple "Automobile", "Bricolage", "Santé"...), en réutilisant si \
possible une thématique de la liste ci-dessous plutôt que d'en créer une \
nouvelle proche d'une existante (par exemple ne crée pas "Voitures" si \
"Automobile" existe déjà et convient).

Thématiques déjà utilisées ailleurs dans la bibliothèque :
{vocabulary}

Réponds avec exactement un élément par numéro ci-dessous, dans n'importe \
quel ordre, en reprenant son magazine_id exact.

"""


def extract_sommaires_batch(db: Session, magazines_with_pages: list[tuple[Magazine, list[Page]]]) -> dict[int, dict]:
    """Extracts the sommaire and themes for several magazines in a SINGLE
    Gemini request, instead of one request per magazine per concern (two
    requests per magazine previously - one for the sommaire, one for
    themes). The account's quota is request-count-limited (e.g. the Gemini
    free tier's 20 requests/day), not token-limited, so batching many
    magazines' text into one larger request is far cheaper than many small
    ones covering the exact same content.

    Returns {magazine_id: {"articles": [...], "themes": [...]}}. Raises on
    a whole-batch failure (missing API key, no OCR'd text at all across the
    batch, quota exhausted, malformed response) - the caller marks every
    magazine in the batch as failed with that one error, since a
    batch-level failure can't be attributed to a single magazine within it.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY non configurée")

    sections = []
    any_text = False
    for magazine, pages in magazines_with_pages:
        candidate_pages = [p for p in pages if p.page_number <= MAX_SOMMAIRE_PAGE and p.raw_text]
        if candidate_pages:
            any_text = True
        text = "\n\n".join(f"--- Page {p.page_number} ---\n{p.raw_text}" for p in candidate_pages)
        sections.append(f"=== Magazine {magazine.id} ===\n{text or '(aucun texte OCR disponible)'}")

    if not any_text:
        raise RuntimeError("Aucun texte OCR disponible sur les premières pages")

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
        logger.error("Gemini returned non-JSON batch response: %r", (response.text or "")[:500])
        raise RuntimeError("Réponse Gemini invalide (JSON illisible)") from exc

    if not isinstance(data, list):
        raise RuntimeError("Réponse Gemini invalide (format inattendu)")

    results: dict[int, dict] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        magazine_id = item.get("magazine_id")
        if not isinstance(magazine_id, int):
            continue

        articles = []
        for entry in item.get("articles") or []:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            page = entry.get("page")
            if title and isinstance(page, int) and page >= 1:
                articles.append({"title": title, "start_page": page})

        themes = [str(t).strip() for t in (item.get("themes") or []) if str(t).strip()][:MAX_THEMES_PER_MAGAZINE]
        results[magazine_id] = {"articles": articles, "themes": themes}

    return results
