"""Construction du corpus soumis à un modèle de langage externe pour en tirer
la taxonomie à deux niveaux.

Partagé entre l'outil en ligne de commande et l'API d'administration : une
seule implémentation, donc un seul format à maintenir. Le fichier téléchargé
depuis l'admin est exactement celui que produit le script.

UN SEUL FICHIER, GROUPÉ PAR COLLECTION. Deux raisons, tirées de l'expérience :

  - Un export par thématique de numéro versait tous les articles d'un numéro
    dans chacune de ses thématiques. Un « 60 Millions » étiqueté
    [Consommation, Santé, Animaux] mettait ses vingt titres dans les trois
    corpus, au point que le fichier « Animaux » parlait surtout de soins
    dentaires et de chardonnay.

  - Un découpage par collection traitée séparément fait diverger la taxonomie :
    une collection rend « Alimentation > budget », une autre « Budget >
    alimentation », et rien ne les réconcilie. En une seule passe, le modèle
    voit tout et produit une arborescence cohérente.

Le groupement par collection reste présent dans le fichier : il donne au
modèle le contexte éditorial sans mélanger les corpus.

LECTURE SEULE : rien ici n'écrit en base.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Article, Collection, Magazine

CONSIGNE = (
    "Tu recois les titres d'articles d'une bibliotheque de magazines, groupes "
    "par collection. Construis une taxonomie a DEUX niveaux : des thematiques "
    "(ex. « Alimentation », « Audio », « Fiscalite ») et, sous chacune, ses "
    "sous-thematiques concretes (ex. « legumes », « budget alimentaire »). "
    "Vise 5 a 12 sous-thematiques par thematique.\n\n"
    "Reponds UNIQUEMENT par un JSON de la forme :\n"
    '{"thematiques": [{"nom": "Alimentation", "sous_thematiques": '
    '[{"nom": "Legumes", "mots_cles": ["legume", "potager", "maraicher"]}]}]}\n\n'
    "Les mots-cles doivent etre des expressions REELLEMENT presentes dans les "
    "titres : ils servent a rattacher automatiquement chaque article, et un "
    "mot-cle absent du corpus ne rattachera rien. Prefere le singulier, le "
    "pluriel est gere automatiquement.\n\n"
    "Si la reponse depasse ta limite de sortie, rends un sous-ensemble complet "
    "et valide des thematiques plutot qu'un JSON tronque : l'import est "
    "cumulatif, tu pourras livrer le reste ensuite."
)


def corpus_par_collection(db: Session) -> list[dict]:
    """Titres d'articles par collection, dédoublonnés au sein de chacune.

    Le dédoublonnage a lieu ici plutôt que côté modèle : un même titre répété
    dans quarante numéros n'aide en rien à identifier les regroupements, et
    gonfle l'invite d'autant.

    Les collections sans aucun article sont omises — onze d'entre elles sont
    dans ce cas, et une entrée vide n'apprendrait rien au modèle.
    """
    lignes = (
        db.query(Collection.name, Article.title, Magazine.id)
        .join(Magazine, Magazine.collection_id == Collection.id)
        .join(Article, Article.magazine_id == Magazine.id)
        .order_by(Collection.name)
        .all()
    )

    par_collection: dict[str, dict] = {}
    for nom_collection, titre, magazine_id in lignes:
        propre = (titre or "").strip()
        if not propre:
            continue
        entree = par_collection.setdefault(
            nom_collection, {"nom": nom_collection, "numeros": set(), "vus": set(), "titres": []}
        )
        entree["numeros"].add(magazine_id)
        cle = propre.casefold()
        if cle in entree["vus"]:
            continue
        entree["vus"].add(cle)
        entree["titres"].append(propre)

    resultat = []
    for entree in par_collection.values():
        resultat.append(
            {
                "nom": entree["nom"],
                "numeros": len(entree["numeros"]),
                "titres": entree["titres"],
            }
        )
    # La plus fournie d'abord : si le modele doit tronquer, autant qu'il
    # commence par ce qui pese le plus.
    resultat.sort(key=lambda c: len(c["titres"]), reverse=True)
    return resultat


def charge_utile(db: Session) -> dict:
    """Le fichier unique destiné au modèle."""
    collections = corpus_par_collection(db)
    titres_uniques = sum(len(c["titres"]) for c in collections)
    return {
        "consigne": CONSIGNE,
        "collections_exportees": len(collections),
        "titres_uniques": titres_uniques,
        # Sert a juger si le corpus tient dans une invite : au-dela d'environ
        # 150 000 jetons, il faudra le decouper.
        "caracteres_titres": sum(len(t) for c in collections for t in c["titres"]),
        "collections": collections,
    }


def resume(db: Session) -> dict:
    """Volumétrie seule, pour l'affichage admin — sans charger tous les titres."""
    total_articles = db.query(func.count(Article.id)).scalar() or 0
    collections_avec_articles = (
        db.query(func.count(func.distinct(Collection.id)))
        .join(Magazine, Magazine.collection_id == Collection.id)
        .join(Article, Article.magazine_id == Magazine.id)
        .scalar()
        or 0
    )
    return {
        "articles": total_articles,
        "collections": collections_avec_articles,
    }


def nom_de_fichier() -> str:
    """Nom du fichier téléchargé. Sans caractère à échapper dans un en-tête."""
    return "taxonomie_corpus.json"
