from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Setting

# The sommaire (table of contents) is almost always within the first few
# pages; capping what we send keeps the prompt small and cheap.
MAX_SOMMAIRE_PAGE = 8

GEMINI_MODEL_SETTING_KEY = "gemini_model"

# Curated choices offered in the admin UI. gemini_model still accepts any
# string, so an admin can type a different model id if needed.
AVAILABLE_GEMINI_MODELS = [
    {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash (rapide, par défaut)"},
    {"id": "gemini-3.1-pro", "label": "Gemini 3.1 Pro (plus précis, plus lent)"},
    {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite (le moins cher)"},
]


def get_gemini_model(db: Session) -> str:
    row = db.get(Setting, GEMINI_MODEL_SETTING_KEY)
    if row and row.value:
        return row.value
    return get_settings().gemini_model


def set_gemini_model(db: Session, model: str) -> None:
    row = db.get(Setting, GEMINI_MODEL_SETTING_KEY)
    if row:
        row.value = model
    else:
        db.add(Setting(key=GEMINI_MODEL_SETTING_KEY, value=model))
    db.commit()
