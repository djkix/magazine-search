import json
import logging

from google import genai
from google.genai import types

from app.config import get_settings
from app.models import Magazine, Page

logger = logging.getLogger("app.toc")

# The sommaire (table of contents) is almost always within the first few
# pages; capping what we send keeps the prompt small and cheap.
MAX_SOMMAIRE_PAGE = 8

PROMPT = """Tu reçois le texte OCR des premières pages d'un magazine français. \
Une de ces pages est probablement le "sommaire" (table des matières), qui liste \
les articles du numéro avec leur page de début, souvent sous la forme \
"Titre de l'article ..... 12".

Extrait uniquement les articles listés dans ce sommaire. Si aucun sommaire \
n'est identifiable dans ce texte, renvoie une liste vide."""

ARTICLE_LIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "page": {"type": "integer"},
        },
        "required": ["title", "page"],
    },
}


def extract_toc(magazine: Magazine, pages: list[Page]) -> list[dict]:
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not configured, skipping TOC extraction for magazine %s", magazine.id)
        return []

    candidate_pages = [p for p in pages if p.page_number <= MAX_SOMMAIRE_PAGE and p.raw_text]
    text = "\n\n".join(f"--- Page {p.page_number} ---\n{p.raw_text}" for p in candidate_pages)
    if not text.strip():
        return []

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{PROMPT}\n\n{text}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=ARTICLE_LIST_SCHEMA,
        ),
    )

    try:
        data = json.loads(response.text or "[]")
    except json.JSONDecodeError:
        logger.error("Gemini returned non-JSON TOC response for magazine %s: %r", magazine.id, (response.text or "")[:500])
        return []

    if not isinstance(data, list):
        return []

    articles = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        page = item.get("page")
        if not title or not isinstance(page, int) or page < 1:
            continue
        articles.append({"title": title, "start_page": page})
    return articles
