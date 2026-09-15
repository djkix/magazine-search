"""Injection de la taxonomie produite hors ligne, et rattachement des articles
à partir des mots-clés.

Partagé entre l'outil en ligne de commande et l'API d'administration. Les
fonctions RENDENT un compte rendu structuré au lieu de l'afficher : le script
le met en forme pour le terminal, l'API le renvoie au navigateur. Une seule
logique, donc un seul comportement à vérifier.

Deux niveaux, rattachés aux ARTICLES :

    Thématique (Alimentation) -> Sous-thématique (légumes) -> Articles

Le modèle ne fait que NOMMER les regroupements et fournir leurs mots-clés ; le
rattachement est calculé ici. C'est ce qui permet à un numéro scanné demain de
rejoindre seul les sous-thématiques existantes, sans nouvel appel payant.

L'import est CUMULATIF : plusieurs fichiers successifs s'ajoutent. Sur un
corpus de cette taille, la réponse d'un modèle arrive souvent en plusieurs
morceaux — exiger un fichier unique et complet rendrait l'opération
impraticable.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, Subtheme, Theme, subtheme_articles
from app.services.sous_thematiques import (
    articles_correspondants,
    motifs_des_mots_cles,
    mots_cles_steriles,
    normaliser,
)
from app.services.themes_des_tags import theme_pour_nom

_MOT_RE = re.compile(r"[a-z0-9]+")

# Mots trop courants pour dire quoi que ce soit d'un sujet. Sans ce filtre, le
# classement des orphelins ne remonterait que « pour », « avec » et « dans ».
# Volontairement court : on ne cherche pas l'exhaustivite linguistique, juste a
# degager les termes porteurs.
_MOTS_VIDES = {
    "avec", "sans", "pour", "dans", "chez", "tout", "tous", "toute", "toutes",
    "plus", "moins", "bien", "cette", "cet", "ces", "leur", "leurs", "notre",
    "nos", "votre", "vos", "mais", "donc", "quand", "comme", "faire", "fait",
    "etre", "avoir", "peut", "faut", "sont", "ont", "une", "des", "les", "que",
    "qui", "quoi", "dont", "vous", "nous", "elle", "elles", "ils",
    "the", "and", "for", "with", "your", "you", "our", "this", "that", "from",
    "how", "what", "why", "all", "new", "best", "get", "are", "can", "has",
}


class ImportInvalide(ValueError):
    """Charge utile mal formée."""


def corpus_articles(db: Session) -> list[tuple[int, str]]:
    """(article_id, titre) de toute la bibliothèque.

    La taxonomie est globale : un mot-clé s'applique à n'importe quel article,
    quelle que soit la collection. Restreindre le corpus par thématique de
    numéro, comme le faisait la première version, reproduisait la
    contamination qu'on cherche justement à supprimer.
    """
    return db.query(Article.id, Article.title).all()


def rattacher(
    db: Session, sous_theme: Subtheme, corpus: list[tuple[int, str]], appliquer: bool
) -> dict:
    """Recalcule les articles d'une sous-thématique. Rend un compte rendu."""
    motifs = motifs_des_mots_cles(sous_theme.keywords)
    steriles = mots_cles_steriles(sous_theme.keywords, [titre for _, titre in corpus])
    retenus = articles_correspondants(motifs, corpus)

    if appliquer:
        db.execute(
            subtheme_articles.delete().where(subtheme_articles.c.subtheme_id == sous_theme.id)
        )
        if retenus:
            db.execute(
                subtheme_articles.insert(),
                [{"subtheme_id": sous_theme.id, "article_id": aid} for aid in retenus],
            )

    return {
        "nom": sous_theme.name,
        "articles": len(retenus),
        "mots_cles_steriles": steriles,
        # Retiré avant restitution : sert seulement au calcul de la couverture.
        "articles_ids": retenus,
    }


def importer(db: Session, charge: dict, appliquer: bool) -> dict:
    """Injecte une taxonomie et rend un compte rendu.

    N'ÉCRIT RIEN si `appliquer` est faux : la transaction est annulée en fin
    de parcours. C'est le mode par défaut partout — la simulation doit être le
    chemin naturel, pas une option qu'on pense à demander.

    Format attendu :

        {"thematiques": [
            {"nom": "Alimentation",
             "sous_thematiques": [
                {"nom": "Legumes", "mots_cles": ["legume", "potager"]}
             ]}
        ]}

    CUMULATIF : les sous-thématiques absentes du fichier ne sont pas
    supprimées. Un envoi en plusieurs morceaux enrichit donc la taxonomie au
    lieu de l'écraser à chaque fois.
    """
    if not isinstance(charge, dict):
        raise ImportInvalide("Le fichier doit contenir un objet JSON.")

    thematiques = charge.get("thematiques")
    if not isinstance(thematiques, list) or not thematiques:
        raise ImportInvalide(
            "Format attendu : un objet avec « thematiques », une liste non vide."
        )

    corpus = corpus_articles(db)
    rapports: list[dict] = []
    ignorees: list[str] = []
    couverts: set[int] = set()

    for entree_theme in thematiques:
        if not isinstance(entree_theme, dict):
            ignorees.append(str(entree_theme)[:80])
            continue
        nom_theme = (entree_theme.get("nom") or "").strip()
        sous = entree_theme.get("sous_thematiques")
        if not nom_theme or not isinstance(sous, list):
            ignorees.append(nom_theme or str(entree_theme)[:80])
            continue

        theme = theme_pour_nom(db, nom_theme)

        for entree in sous:
            if not isinstance(entree, dict):
                ignorees.append(str(entree)[:80])
                continue
            nom = (entree.get("nom") or "").strip()
            mots_cles = [str(m).strip() for m in (entree.get("mots_cles") or []) if str(m).strip()]
            if not nom or not mots_cles:
                ignorees.append(nom or str(entree)[:80])
                continue

            sous_theme = (
                db.query(Subtheme)
                .filter(Subtheme.theme_id == theme.id, Subtheme.name == nom)
                .first()
            )
            if sous_theme is None:
                sous_theme = Subtheme(theme_id=theme.id, name=nom, keywords=mots_cles)
                db.add(sous_theme)
                # flush() attribue un identifiant sans valider : indispensable
                # pour rattacher, et annulable en simulation.
                db.flush()
            else:
                sous_theme.keywords = mots_cles

            rapport = rattacher(db, sous_theme, corpus, appliquer)
            rapport["thematique"] = nom_theme
            couverts |= rapport.pop("articles_ids")
            rapports.append(rapport)

    if appliquer:
        db.commit()
    else:
        db.rollback()

    return {
        "applique": appliquer,
        "articles_corpus": len(corpus),
        "articles_couverts": len(couverts),
        "articles_sans_sous_thematique": len(corpus) - len(couverts),
        "thematiques": len({r["thematique"] for r in rapports}),
        "sous_thematiques": sorted(rapports, key=lambda r: r["articles"], reverse=True),
        "entrees_ignorees": ignorees,
    }


def recalculer_tout(db: Session, appliquer: bool) -> dict:
    """Rejoue le rattachement de toutes les sous-thématiques existantes.

    Aucun modèle n'intervient : les mots-clés sont conservés en base, il suffit
    de les reconfronter au corpus. C'est ce qu'il faut lancer après l'arrivée
    de nouveaux numéros, pour que leurs articles rejoignent les regroupements
    déjà définis.
    """
    sous_themes = db.query(Subtheme).join(Theme).order_by(Theme.name, Subtheme.name).all()
    corpus = corpus_articles(db)

    rapports = []
    couverts: set[int] = set()
    for sous_theme in sous_themes:
        rapport = rattacher(db, sous_theme, corpus, appliquer)
        rapport["thematique"] = sous_theme.theme.name
        couverts |= rapport.pop("articles_ids")
        rapports.append(rapport)

    if appliquer:
        db.commit()
    else:
        db.rollback()

    return {
        "applique": appliquer,
        "articles_corpus": len(corpus),
        "articles_couverts": len(couverts),
        "articles_sans_sous_thematique": len(corpus) - len(couverts),
        "sous_thematiques": rapports,
    }


def rattacher_magazine(db: Session, magazine_id: int) -> dict:
    """Rattache les articles d'un SEUL numéro aux sous-thématiques existantes.

    Appelé à la fin de chaque extraction de sommaire : c'est ce qui fait
    entrer un numéro fraîchement scanné dans la navigation sans intervention,
    et sans le moindre appel à un modèle — les mots-clés sont déjà en base.

    Ne touche qu'aux liens de CE numéro. `rattacher()`, lui, purge une
    sous-thématique entière : l'employer ici effacerait les rattachements de
    toute la bibliothèque à chaque ingestion.

    Coût : quelques dizaines d'articles confrontés aux motifs existants,
    quelques millisecondes. Rien à voir avec un recalcul complet, qui
    reconfronte des milliers de titres.
    """
    articles = (
        db.query(Article.id, Article.title).filter(Article.magazine_id == magazine_id).all()
    )
    if not articles:
        return {"magazine_id": magazine_id, "articles": 0, "rattachements": 0}

    # Purge ciblée : un retraitement du sommaire remplace les articles, et les
    # liens des anciens deviendraient orphelins.
    ids = [aid for aid, _ in articles]
    db.execute(subtheme_articles.delete().where(subtheme_articles.c.article_id.in_(ids)))

    liens: list[dict] = []
    for sous_theme in db.query(Subtheme).all():
        motifs = motifs_des_mots_cles(sous_theme.keywords)
        if not motifs:
            continue
        for article_id in articles_correspondants(motifs, articles):
            liens.append({"subtheme_id": sous_theme.id, "article_id": article_id})

    if liens:
        db.execute(subtheme_articles.insert(), liens)
    db.commit()

    return {
        "magazine_id": magazine_id,
        "articles": len(articles),
        "rattachements": len(liens),
    }


def articles_orphelins(db: Session, limite_mots: int = 40, limite_exemples: int = 30) -> dict:
    """Articles qu'aucune sous-thématique n'attrape, et mots les plus fréquents.

    Sert à enrichir la taxonomie SANS appel à un modèle : si « photovoltaïque »
    revient quarante fois parmi les orphelins et qu'aucun mot-clé ne le couvre,
    le diagnostic ne demande aucune IA.

    Les mots de moins de quatre lettres et les mots vides les plus courants
    sont écartés : sans ce filtre, la liste ne remonterait que « pour », « avec »
    et « dans ».
    """
    rattaches = select(subtheme_articles.c.article_id)
    orphelins = (
        db.query(Article.id, Article.title)
        .filter(Article.id.notin_(rattaches))
        .all()
    )

    frequences: dict[str, int] = {}
    for _, titre in orphelins:
        # Dédoublonnage par titre : un mot répété dans le même titre ne compte
        # qu'une fois, sinon un titre bavard fausserait le classement.
        for mot in set(_MOT_RE.findall(normaliser(titre))):
            if len(mot) < 4 or mot in _MOTS_VIDES:
                continue
            frequences[mot] = frequences.get(mot, 0) + 1

    tries = sorted(frequences.items(), key=lambda kv: kv[1], reverse=True)[:limite_mots]

    total_articles = db.query(func.count(Article.id)).scalar() or 0
    return {
        "articles_total": total_articles,
        "articles_orphelins": len(orphelins),
        "mots_frequents": [{"mot": m, "occurrences": n} for m, n in tries],
        "exemples": [t for _, t in orphelins[:limite_exemples]],
    }
