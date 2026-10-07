from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Theme


def theme_pour_nom(db: Session, nom: str) -> Theme:
    """Le thème portant ce nom, créé au besoin.

    Comparaison insensible à la casse : deux variantes de casse ne doivent
    pas créer deux thèmes distincts côte à côte. La contrainte d'unicité sur
    `themes.name` ne protège, elle, que des doublons exacts.
    """
    theme = db.query(Theme).filter(func.lower(Theme.name) == nom.lower()).first()
    if theme is None:
        theme = Theme(name=nom)
        db.add(theme)
        db.flush()
    return theme
