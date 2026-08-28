import json
import logging

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, Collection, Magazine
from app.services.toc import get_gemini_model

logger = logging.getLogger("app.theme_summary")

# Bounds the prompt size for a collection with an unusually large backlog of
# issues; comfortably above what any real personal collection is expected
# to hold articles for.
MAX_ARTICLES = 2000

PROMPT = """Tu reçois la liste numérotée des articles de tous les numéros \
d'une collection de magazine français. Regroupe ces articles par thématique \
pertinente : invente toi-même les thématiques les plus adaptées au contenu \
(par exemple "Automobile", "Bricolage", "Santé"...). Un article ne doit \
appartenir qu'à une seule thématique. Vise entre 5 et 15 thématiques selon \
la richesse du contenu, en évitant les thématiques fourre-tout ou trop \
fines.

Réponds uniquement avec les regroupements, en référençant chaque article \
par son indice dans la liste ci-dessous."""

THEME_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "theme": {"type": "string"},
            "article_indices": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["theme", "article_indices"],
    },
}


def generate_theme_summary(db: Session, collection: Collection) -> list[dict]:
    """Fetch every article across a collection's issues, ask Gemini to group
    them by theme (referencing articles by index to avoid it hallucinating
    titles/pages), and return the resolved [{theme, articles}] structure -
    the caller is responsible for persisting it."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY non configurée")

    rows = (
        db.query(Article, Magazine.id, Magazine.title)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .filter(Magazine.collection_id == collection.id)
        .order_by(Magazine.publication_date.desc().nulls_last(), Article.start_page)
        .limit(MAX_ARTICLES)
        .all()
    )
    if not rows:
        return []

    articles = [
        {"magazine_id": magazine_id, "magazine_title": magazine_title, "title": article.title, "start_page": article.start_page}
        for article, magazine_id, magazine_title in rows
    ]
    listing = "\n".join(f"{i}. [{a['magazine_title']}] {a['title']}" for i, a in enumerate(articles))

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=get_gemini_model(db),
        contents=f"{PROMPT}\n\n{listing}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=THEME_SCHEMA,
        ),
    )

    try:
        data = json.loads(response.text or "[]")
    except json.JSONDecodeError:
        logger.error(
            "Gemini returned non-JSON theme summary for collection %s: %r", collection.id, (response.text or "")[:500]
        )
        raise RuntimeError("Réponse Gemini invalide")

    if not isinstance(data, list):
        raise RuntimeError("Réponse Gemini invalide")

    themes = []
    seen_indices: set[int] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        theme = str(item.get("theme", "")).strip()
        indices = item.get("article_indices")
        if not theme or not isinstance(indices, list):
            continue

        theme_articles = []
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(articles) or idx in seen_indices:
                continue
            seen_indices.add(idx)
            theme_articles.append(articles[idx])
        if theme_articles:
            themes.append({"theme": theme, "articles": theme_articles})

    return themes
