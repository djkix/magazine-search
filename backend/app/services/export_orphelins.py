"""Corpus des articles non rattachés, destiné à enrichir la taxonomie.

Complément de `export_thematiques`, qui sort la bibliothèque ENTIÈRE pour
construire une taxonomie de zéro. Ici on ne sort que ce qui reste à classer,
avec la taxonomie déjà en place : le modèle n'a plus à réinventer l'existant,
il l'étend.

Deux raisons de séparer les deux exports :

  - le volume. Le corpus complet fait 13 500 titres ; les orphelins en font
    une fraction. Soumettre l'ensemble pour n'obtenir que des ajouts noie le
    signal et coûte du contexte pour rien ;
  - la consigne. Créer une taxonomie et l'étendre sans casser l'existant sont
    deux exercices différents, qui demandent deux prompts différents.

LECTURE SEULE : rien ici n'écrit en base.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, Collection, Magazine, Subtheme, Theme, subtheme_articles

# Consigne embarquée dans le fichier, pour que le modèle la reçoive avec les
# données plutôt que par un copier-coller séparé qu'on finit par oublier.
#
# Les trois contraintes énoncées ne sont pas décoratives : chacune correspond
# à un comportement vérifié du code d'import, et les ignorer produit une
# taxonomie qui s'applique mal ou qui détruit l'existant.
CONSIGNE_ORPHELINS = (
    "Tu enrichis une taxonomie documentaire à deux niveaux (thématique > "
    "sous-thématique) pour une bibliothèque de magazines numérisés.\n"
    "\n"
    "Tu reçois deux choses : `taxonomie_existante`, déjà en place et qui "
    "fonctionne, et `articles_non_rattaches`, les titres qu'aucun mot-clé "
    "actuel n'attrape. Ton travail est de couvrir ces orphelins.\n"
    "\n"
    "RÈGLE 1 — Les mots-clés sont cherchés dans le TITRE de l'article, en "
    "correspondance de mot entier. Seul un « s » ou un « x » final est "
    "toléré : « legume » attrape « legumes », mais « mix » n'attrape PAS "
    "« mixing », et « master » n'attrape PAS « mastering ». Tu dois donc "
    "lister explicitement chaque forme utile, y compris les formes verbales "
    "anglaises.\n"
    "\n"
    "RÈGLE 2 — Si tu reprends une sous-thématique existante pour lui ajouter "
    "des mots-clés, renvoie sa liste COMPLÈTE, anciens mots-clés inclus. "
    "L'import remplace la liste, il ne la fusionne pas : omettre un mot-clé "
    "existant détacherait les articles qu'il retenait.\n"
    "\n"
    "RÈGLE 3 — Évite les mots trop larges. Un mot-clé comme « test » ou "
    "« guide » attraperait des centaines d'articles sans rapport et "
    "polluerait la navigation. Préfère un terme spécifique, quitte à en "
    "lister plusieurs.\n"
    "\n"
    "N'invente pas de sujet absent des titres fournis. Ne renvoie que les "
    "thématiques et sous-thématiques que tu crées ou modifies : l'import est "
    "cumulatif, ce que tu omets reste en place.\n"
    "\n"
    "Réponds UNIQUEMENT par un objet JSON de cette forme, sans commentaire "
    "ni texte autour :\n"
    '{"thematiques": [{"nom": "Alimentation", "sous_thematiques": '
    '[{"nom": "Legumes", "mots_cles": ["legume", "potager", "jardinage"]}]}]}'
)


def taxonomie_existante(db: Session) -> list[dict]:
    """Thématiques, sous-thématiques et mots-clés actuellement en base.

    Fournie au modèle pour qu'il étende au lieu de dupliquer : sans elle, il
    recrée des sous-thématiques déjà présentes sous un nom voisin, et le
    résultat se fragmente.
    """
    lignes = (
        db.query(Theme.name, Subtheme.name, Subtheme.keywords)
        .join(Subtheme, Subtheme.theme_id == Theme.id)
        .order_by(Theme.name, Subtheme.name)
        .all()
    )

    par_theme: dict[str, list[dict]] = {}
    for nom_theme, nom_sous_theme, mots_cles in lignes:
        par_theme.setdefault(nom_theme, []).append(
            {"nom": nom_sous_theme, "mots_cles": list(mots_cles or [])}
        )
    return [
        {"nom": nom, "sous_thematiques": sous_themes} for nom, sous_themes in par_theme.items()
    ]


def orphelins_par_collection(db: Session) -> list[dict]:
    """Titres non rattachés, groupés par collection.

    Le groupement donne au modèle le contexte éditorial : « MIX » ne désigne
    pas la même chose dans un magazine de musique et dans un magazine de
    bricolage.

    Titres DÉDUPLIQUÉS par collection : une rubrique récurrente (« Courrier »,
    « News ») apparaît dans chaque numéro et gonflerait le fichier sans rien
    apprendre de plus au modèle.
    """
    deja_rattaches = select(subtheme_articles.c.article_id)
    lignes = (
        db.query(Collection.name, Article.title)
        .select_from(Article)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .outerjoin(Collection, Collection.id == Magazine.collection_id)
        .filter(Article.id.notin_(deja_rattaches))
        .order_by(Collection.name, Article.title)
        .all()
    )

    par_collection: dict[str, list[str]] = {}
    vus: dict[str, set[str]] = {}
    for nom_collection, titre in lignes:
        cle = nom_collection or "(sans collection)"
        if titre in vus.setdefault(cle, set()):
            continue
        vus[cle].add(titre)
        par_collection.setdefault(cle, []).append(titre)

    return [
        {"nom": nom, "titres": titres, "titres_uniques": len(titres)}
        for nom, titres in par_collection.items()
    ]


def charge_utile(db: Session) -> dict:
    """Fichier complet à soumettre au modèle : consigne, existant, orphelins."""
    return {
        "consigne": CONSIGNE_ORPHELINS,
        "taxonomie_existante": taxonomie_existante(db),
        "articles_non_rattaches": orphelins_par_collection(db),
    }


def resume(db: Session) -> dict:
    """Volumétrie, pour juger avant de télécharger s'il faut découper.

    `caracteres_titres` est la seule mesure qui compte pour dimensionner la
    fenêtre de contexte d'un modèle — le nombre de titres seul ne dit rien de
    leur longueur.
    """
    total_articles = db.query(func.count(Article.id)).scalar() or 0
    deja_rattaches = select(subtheme_articles.c.article_id)
    orphelins = (
        db.query(func.count(Article.id)).filter(Article.id.notin_(deja_rattaches)).scalar() or 0
    )
    groupes = orphelins_par_collection(db)
    titres_uniques = sum(g["titres_uniques"] for g in groupes)
    caracteres = sum(len(t) for g in groupes for t in g["titres"])
    return {
        "articles_total": total_articles,
        "articles_orphelins": orphelins,
        "titres_uniques": titres_uniques,
        "collections": len(groupes),
        "caracteres_titres": caracteres,
    }


def nom_de_fichier() -> str:
    """Nom du fichier téléchargé. Sans caractère à échapper dans un en-tête."""
    return "taxonomie_orphelins.json"
