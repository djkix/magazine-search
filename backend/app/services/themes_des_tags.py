"""Propagation des tags de SUJET vers les thématiques des numéros.

Un tag est posé à la main sur une collection entière : c'est une donnée curée
par l'administrateur, donc plus sûre qu'une inférence de modèle. « Système D »
porte le tag « Bricolage », et cela vaut pour ses 199 numéros, sans exception
et sans consommer le moindre quota.

Seuls les tags marqués `is_subject` sont propagés. Le vocabulaire mélange en
effet deux natures : des sujets (« Bricolage », « Santé ») et des formats
éditoriaux (« Test », « Tutoriel », « Guide achat »). Propager les seconds
donnerait une navigation par sujet où « Test » écraserait tout.

La propagation ne renseigne PAS `themed_at` : les numéros restent dans la file
de thématisation, et Gemini viendra affiner par la suite. Le tag fournit le
socle garanti, le modèle l'enrichit — d'où la fusion opérée par
`fusionner_themes`, sans laquelle le premier passage de Gemini effacerait le
thème hérité du tag.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Collection, Magazine, Tag, Theme, collection_tags


def theme_pour_nom(db: Session, nom: str) -> Theme:
    """Le thème portant ce nom, créé au besoin.

    Comparaison insensible à la casse : un tag « Bricolage » ne doit pas créer
    un second thème à côté d'un « bricolage » déjà produit par Gemini. La
    contrainte d'unicité sur `themes.name` ne protège, elle, que des doublons
    exacts.
    """
    theme = db.query(Theme).filter(func.lower(Theme.name) == nom.lower()).first()
    if theme is None:
        theme = Theme(name=nom)
        db.add(theme)
        db.flush()
    return theme


def tags_sujets_du_magazine(db: Session, magazine: Magazine) -> list[Tag]:
    """Tags de sujet portés par la collection du numéro."""
    if magazine.collection_id is None:
        return []
    return (
        db.query(Tag)
        .join(collection_tags, collection_tags.c.tag_id == Tag.id)
        .filter(collection_tags.c.collection_id == magazine.collection_id, Tag.is_subject.is_(True))
        .all()
    )


def fusionner_themes(db: Session, magazine: Magazine, themes_modele: list[Theme]) -> list[Theme]:
    """Thèmes du modèle, complétés de ceux hérités des tags de sujet.

    Appelé au moment où Gemini attribue ses thèmes. Sans cette fusion,
    l'affectation écraserait la liste et ferait disparaître le thème garanti
    par le tag de collection — un numéro de « Système D » perdrait
    « Bricolage » au premier passage du modèle.
    """
    fusion: list[Theme] = []
    vus: set[int] = set()
    for theme in themes_modele + [theme_pour_nom(db, t.name) for t in tags_sujets_du_magazine(db, magazine)]:
        if theme.id in vus:
            continue
        vus.add(theme.id)
        fusion.append(theme)
    return fusion


def propager(db: Session, appliquer: bool) -> dict:
    """Attache à chaque numéro les thèmes hérités des tags de sujet.

    Idempotent : un numéro déjà rattaché n'est pas retouché. N'écrit rien si
    `appliquer` est faux.
    """
    tags = db.query(Tag).filter(Tag.is_subject.is_(True)).order_by(Tag.name).all()
    rapports = []

    for tag in tags:
        theme = theme_pour_nom(db, tag.name)
        magazines = (
            db.query(Magazine)
            .join(Collection, Collection.id == Magazine.collection_id)
            .join(collection_tags, collection_tags.c.collection_id == Collection.id)
            .filter(collection_tags.c.tag_id == tag.id)
            .all()
        )

        ajoutes = 0
        for magazine in magazines:
            if any(t.id == theme.id for t in magazine.themes):
                continue
            ajoutes += 1
            if appliquer:
                magazine.themes.append(theme)

        rapports.append(
            {
                "tag": tag.name,
                "numeros_concernes": len(magazines),
                "rattachements_ajoutes": ajoutes,
            }
        )

    if appliquer:
        db.commit()
    else:
        db.rollback()

    return {
        "applique": appliquer,
        "tags_sujets": len(tags),
        "details": rapports,
        "total_ajoutes": sum(r["rattachements_ajoutes"] for r in rapports),
    }
