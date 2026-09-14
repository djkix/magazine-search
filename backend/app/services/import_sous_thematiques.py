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

from sqlalchemy.orm import Session

from app.models import Article, Subtheme, Theme, subtheme_articles
from app.services.sous_thematiques import (
    articles_correspondants,
    motifs_des_mots_cles,
    mots_cles_steriles,
)
from app.services.themes_des_tags import theme_pour_nom


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
