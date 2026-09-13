"""Injection des sous-thématiques produites hors ligne, et rattachement des
numéros à partir de leurs mots-clés.

Partagé entre l'outil en ligne de commande et l'API d'administration. Les
fonctions RENDENT un compte rendu structuré au lieu de l'afficher : le script
le met en forme pour le terminal, l'API le renvoie tel quel au navigateur.
Une seule logique, donc un seul comportement à vérifier.

Le modèle de langage ne fait que NOMMER les regroupements et proposer leurs
mots-clés. Le rattachement est calculé ici, localement, ce qui le rend
vérifiable et rejouable gratuitement quand la bibliothèque s'enrichit.
"""

from sqlalchemy.orm import Session

from app.models import Article, Magazine, Subtheme, Theme, subtheme_magazines, theme_magazines
from app.services.sous_thematiques import (
    compter_par_numero,
    motifs_des_mots_cles,
    mots_cles_steriles,
)

# Au-delà, le découpage proposé laisse trop de numéros hors de toute
# sous-thématique pour être exploitable : l'interface le signale au lieu de
# laisser croire à un import réussi.
PART_ORPHELINS_SUSPECTE = 1 / 3


class ImportInvalide(ValueError):
    """Charge utile mal formée, ou thématique inconnue en base."""


def articles_de_la_thematique(db: Session, theme_id: int) -> list[tuple[int, str]]:
    """(magazine_id, titre) des articles des numéros portant la thématique.

    Restreint à ces numéros : un article « crème solaire » paru dans un
    magazine d'informatique non étiqueté « Santé » n'a rien à faire sous
    « Santé > Crème solaire ».
    """
    return (
        db.query(Article.magazine_id, Article.title)
        .join(Magazine, Magazine.id == Article.magazine_id)
        .join(theme_magazines, theme_magazines.c.magazine_id == Magazine.id)
        .filter(theme_magazines.c.theme_id == theme_id)
        .all()
    )


def rattacher(
    db: Session, sous_theme: Subtheme, articles: list[tuple[int, str]], appliquer: bool
) -> dict:
    """Recalcule les rattachements d'une sous-thématique. Rend un compte rendu."""
    motifs = motifs_des_mots_cles(sous_theme.keywords)
    steriles = mots_cles_steriles(sous_theme.keywords, [titre for _, titre in articles])
    comptes = compter_par_numero(motifs, articles) if motifs else {}

    if appliquer:
        db.execute(
            subtheme_magazines.delete().where(subtheme_magazines.c.subtheme_id == sous_theme.id)
        )
        if comptes:
            db.execute(
                subtheme_magazines.insert(),
                [
                    {"subtheme_id": sous_theme.id, "magazine_id": mid, "occurrences": n}
                    for mid, n in comptes.items()
                ],
            )

    return {
        "nom": sous_theme.name,
        "numeros": len(comptes),
        "articles": sum(comptes.values()),
        "mots_cles_steriles": steriles,
        # Sert à calculer, en fin d'import, les numéros qu'aucune
        # sous-thématique ne couvre — ceux qui relèveront d'« Autres ».
        "numeros_ids": set(comptes),
    }


def importer(db: Session, charge: dict, appliquer: bool) -> dict:
    """Injecte les sous-thématiques d'une thématique et rend un compte rendu.

    N'ÉCRIT RIEN si `appliquer` est faux : la transaction est annulée en fin
    de parcours. C'est le mode par défaut partout — la simulation doit être
    le chemin naturel, pas une option qu'on pense à demander.

    Lève ImportInvalide si la charge utile est mal formée ou si la thématique
    n'existe pas : mieux vaut refuser que d'écrire à moitié.
    """
    if not isinstance(charge, dict):
        raise ImportInvalide("Le fichier doit contenir un objet JSON.")

    nom_theme = (charge.get("thematique") or "").strip()
    entrees = charge.get("sous_thematiques")
    if not nom_theme or not isinstance(entrees, list):
        raise ImportInvalide(
            "Format attendu : un objet avec « thematique » (texte) et "
            "« sous_thematiques » (liste)."
        )

    theme = db.query(Theme).filter(Theme.name == nom_theme).first()
    if theme is None:
        raise ImportInvalide("Thématique inconnue en base : « %s »." % nom_theme)

    articles = articles_de_la_thematique(db, theme.id)

    noms_recus: list[str] = []
    rapports: list[dict] = []
    ignorees: list[str] = []

    for entree in entrees:
        if not isinstance(entree, dict):
            ignorees.append(str(entree)[:80])
            continue
        nom = (entree.get("nom") or "").strip()
        mots_cles = [str(m).strip() for m in (entree.get("mots_cles") or []) if str(m).strip()]
        if not nom or not mots_cles:
            ignorees.append(nom or str(entree)[:80])
            continue
        noms_recus.append(nom)

        sous_theme = (
            db.query(Subtheme).filter(Subtheme.theme_id == theme.id, Subtheme.name == nom).first()
        )
        if sous_theme is None:
            sous_theme = Subtheme(theme_id=theme.id, name=nom, keywords=mots_cles)
            db.add(sous_theme)
            # flush() donne un identifiant sans valider : necessaire pour
            # rattacher, et annulable si l'on est en simulation.
            db.flush()
        else:
            sous_theme.keywords = mots_cles

        rapports.append(rattacher(db, sous_theme, articles, appliquer))

    obsoletes = (
        [
            s.name
            for s in db.query(Subtheme)
            .filter(Subtheme.theme_id == theme.id, Subtheme.name.notin_(noms_recus))
            .all()
        ]
        if noms_recus
        else []
    )
    if appliquer and obsoletes:
        db.query(Subtheme).filter(
            Subtheme.theme_id == theme.id, Subtheme.name.in_(obsoletes)
        ).delete(synchronize_session=False)

    ids_theme = {mid for mid, _ in articles}
    couverts: set[int] = set()
    for rapport in rapports:
        couverts |= rapport["numeros_ids"]
        # Retiré du compte rendu rendu à l'appelant : un ensemble d'entiers
        # n'est pas sérialisable en JSON, et n'intéresse personne à l'écran.
        del rapport["numeros_ids"]

    orphelins = len(ids_theme - couverts)

    if appliquer:
        db.commit()
    else:
        db.rollback()

    return {
        "thematique": nom_theme,
        "applique": appliquer,
        "articles_corpus": len(articles),
        "sous_thematiques": sorted(rapports, key=lambda r: r["articles"], reverse=True),
        "entrees_ignorees": ignorees,
        "obsoletes": obsoletes,
        "numeros_thematique": len(ids_theme),
        "numeros_rattaches": len(couverts),
        "numeros_autres": orphelins,
        # Un découpage qui laisse plus d'un tiers des numéros de côté est
        # probablement trop étroit : mieux vaut relancer le modèle que de
        # publier une navigation trouée.
        "decoupage_suspect": bool(ids_theme) and orphelins > len(ids_theme) * PART_ORPHELINS_SUSPECTE,
    }


def recalculer_tout(db: Session, appliquer: bool) -> dict:
    """Rejoue le rattachement de toutes les sous-thématiques existantes.

    Aucun modèle n'intervient : les mots-clés sont conservés avec chaque
    sous-thématique, il suffit de les reconfronter au corpus. C'est ce qu'il
    faut lancer après l'arrivée de nouveaux numéros.
    """
    sous_themes = db.query(Subtheme).join(Theme).order_by(Theme.name, Subtheme.name).all()

    # Le corpus est chargé une fois par thématique, pas une fois par
    # sous-thématique : sans ce cache, dix sous-thématiques reliraient dix
    # fois les mêmes milliers d'articles.
    corpus: dict[int, list[tuple[int, str]]] = {}
    rapports: list[dict] = []

    for sous_theme in sous_themes:
        if sous_theme.theme_id not in corpus:
            corpus[sous_theme.theme_id] = articles_de_la_thematique(db, sous_theme.theme_id)
        rapport = rattacher(db, sous_theme, corpus[sous_theme.theme_id], appliquer)
        rapport["thematique"] = sous_theme.theme.name
        del rapport["numeros_ids"]
        rapports.append(rapport)

    if appliquer:
        db.commit()
    else:
        db.rollback()

    return {"applique": appliquer, "sous_thematiques": rapports}
