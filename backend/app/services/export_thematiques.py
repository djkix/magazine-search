"""Construction des fichiers d'export soumis à un modèle de langage externe
pour en tirer des sous-thématiques.

Partagé entre l'outil en ligne de commande (tools/exporter_thematiques.py) et
l'API d'administration : une seule implémentation, donc un seul format à
maintenir. Le contenu servi par le bouton « Télécharger » de l'admin est
exactement celui que produit le script.

LECTURE SEULE : rien ici n'écrit en base.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Article, Magazine, Theme, theme_magazines

# En deçà, une thématique n'a pas de sous-structure exploitable : la
# navigation affiche directement ses numéros.
MIN_NUMEROS_POUR_SOUS_THEMATIQUES = 8

# Consigne embarquée dans le fichier, pour n'avoir rien à retenir au moment de
# solliciter le modèle. Elle insiste sur le point qui décide de la qualité du
# résultat : des mots-clés absents du corpus ne rattacheront aucun numéro.
CONSIGNE = (
    "Regroupe ces titres d'articles en 5 a 12 sous-thematiques concretes. "
    "Reponds UNIQUEMENT par un JSON de la forme "
    '{"thematique": "<nom>", "sous_thematiques": '
    '[{"nom": "...", "mots_cles": ["...", "..."]}]}. '
    "Les mots-cles doivent etre des expressions REELLEMENT presentes dans les "
    "titres : ils servent a rattacher automatiquement les numeros, un mot-cle "
    "absent du corpus ne rattachera rien."
)


def titres_de_la_thematique(db: Session, theme_id: int) -> list[str]:
    """Titres d'articles des numéros portant cette thématique, dédoublonnés.

    Le dédoublonnage a lieu ici plutôt que côté modèle : un même titre répété
    dans quarante numéros n'aide en rien à identifier les regroupements, et
    gonfle l'invite d'autant.
    """
    lignes = (
        db.query(Article.title)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .join(theme_magazines, theme_magazines.c.magazine_id == Magazine.id)
        .filter(theme_magazines.c.theme_id == theme_id)
        .all()
    )
    vus: set[str] = set()
    titres: list[str] = []
    for (titre,) in lignes:
        propre = (titre or "").strip()
        if not propre:
            continue
        cle = propre.casefold()
        if cle in vus:
            continue
        vus.add(cle)
        titres.append(propre)
    return titres


def inventaire(db: Session) -> list[tuple[int, str, int]]:
    """(id, nom, nombre de numéros) par thématique, la plus fournie d'abord."""
    return (
        db.query(Theme.id, Theme.name, func.count(Magazine.id.distinct()))
        .join(theme_magazines, theme_magazines.c.theme_id == Theme.id)
        .join(Magazine, Magazine.id == theme_magazines.c.magazine_id)
        .group_by(Theme.id, Theme.name)
        .order_by(func.count(Magazine.id.distinct()).desc(), Theme.name)
        .all()
    )


def inventaire_avec_titres(db: Session) -> list[tuple[int, str, int, int]]:
    """(id, nom, numéros, titres distincts) par thématique, en UNE requête.

    Le décompte se fait en SQL plutôt qu'en chargeant les titres pour les
    compter : l'inventaire complet représente plusieurs milliers de lignes,
    inutiles ici puisqu'on n'affiche qu'un nombre.
    """
    return (
        db.query(
            Theme.id,
            Theme.name,
            func.count(Magazine.id.distinct()),
            func.count(func.distinct(func.lower(Article.title))),
        )
        .join(theme_magazines, theme_magazines.c.theme_id == Theme.id)
        .join(Magazine, Magazine.id == theme_magazines.c.magazine_id)
        .outerjoin(Article, Article.magazine_id == Magazine.id)
        .group_by(Theme.id, Theme.name)
        .order_by(func.count(Magazine.id.distinct()).desc(), Theme.name)
        .all()
    )


def charge_utile(
    db: Session, theme_id: int, nom: str, numeros: int, max_titres: int | None = None
) -> dict:
    """Le fichier destiné au modèle, pour une thématique."""
    titres = titres_de_la_thematique(db, theme_id)
    tronque = max_titres is not None and len(titres) > max_titres
    return {
        "thematique": nom,
        "numeros": numeros,
        "titres_total": len(titres),
        # Signalé explicitement plutôt que tronqué en silence : un découpage
        # établi sur un échantillon ne couvre pas le reste du corpus, et il
        # faut le savoir en lisant le résultat.
        "titres_tronques": tronque,
        "consigne": CONSIGNE,
        "titres": titres[:max_titres] if tronque else titres,
    }


def nom_de_fichier(nom_theme: str) -> str:
    """Nom de fichier sûr pour une thématique.

    Les noms peuvent contenir espaces, accents ou barre oblique — cette
    dernière ouvrant un chemin arbitraire dans un en-tête de téléchargement.
    """
    sur = "".join(c if c.isalnum() else "_" for c in nom_theme).strip("_")
    return "thematique_%s.json" % (sur or "sans_nom")
