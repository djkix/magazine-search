#!/usr/bin/env python3
"""Injecte les sous-thématiques produites hors ligne, et recalcule le
rattachement des numéros à partir de leurs mots-clés.

EN SIMULATION PAR DÉFAUT : sans --appliquer, rien n'est écrit. Le script
affiche ce qu'il ferait, et c'est cette sortie qu'il faut lire avant d'écrire
quoi que ce soit.

Le modèle de langage ne fait que NOMMER les regroupements et proposer leurs
mots-clés. Le rattachement, lui, est calculé ici, localement : le nombre
d'articles correspondants est ainsi vérifiable, explicable, et rejouable
gratuitement quand de nouveaux numéros entrent dans la bibliothèque.

Format attendu (ce que doit produire le modèle) :

    {
      "thematique": "Santé",
      "sous_thematiques": [
        {"nom": "Crème solaire",
         "mots_cles": ["crème solaire", "protection solaire", "indice SPF"]},
        {"nom": "Sommeil et somnifères",
         "mots_cles": ["somnifère", "mélatonine", "insomnie"]}
      ]
    }

Usage, depuis l'hôte :

    docker compose exec app-backend python tools/importer_sous_thematiques.py -f /data/exports/sante.json
    docker compose exec app-backend python tools/importer_sous_thematiques.py -f ... --appliquer
    docker compose exec app-backend python tools/importer_sous_thematiques.py --recalculer-tout --appliquer

--recalculer-tout rejoue le rattachement de toutes les sous-thématiques déjà
en base, sans fichier ni modèle : c'est ce qu'il faut lancer après l'arrivée
de nouveaux numéros.
"""

import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.models import Article, Magazine, Subtheme, Theme, subtheme_magazines, theme_magazines
from app.services.sous_thematiques import (
    compter_par_numero,
    motifs_des_mots_cles,
    mots_cles_steriles,
)


def articles_de_la_thematique(db, theme_id: int) -> list[tuple[int, str]]:
    """(magazine_id, titre) des articles des numéros portant la thématique.

    Restreint à ces numéros-là : un article « crème solaire » paru dans un
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


def rattacher(db, sous_theme: Subtheme, articles: list[tuple[int, str]], appliquer: bool) -> dict:
    """Recalcule les rattachements d'une sous-thématique. Rend un compte rendu."""
    motifs = motifs_des_mots_cles(sous_theme.keywords)
    # Un mot-clé sans correspondance signale que le modèle a inventé un
    # regroupement absent du corpus. Sans cette remontée, la sous-thématique
    # serait simplement vide, sans que rien n'explique pourquoi.
    steriles = mots_cles_steriles(sous_theme.keywords, [titre for _, titre in articles])

    comptes = compter_par_numero(motifs, articles) if motifs else {}

    if appliquer:
        db.execute(subtheme_magazines.delete().where(subtheme_magazines.c.subtheme_id == sous_theme.id))
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
        # Conservé pour calculer, en fin d'import, les numéros que AUCUNE
        # sous-thématique ne couvre — ceux qui tomberaient dans « Autres ».
        "numeros_ids": set(comptes),
    }


def importer_fichier(db, chemin: Path, appliquer: bool) -> int:
    try:
        charge = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("Fichier illisible : %s" % exc, file=sys.stderr)
        return 1

    nom_theme = (charge.get("thematique") or "").strip()
    entrees = charge.get("sous_thematiques")
    if not nom_theme or not isinstance(entrees, list):
        print("Format invalide : il faut 'thematique' et 'sous_thematiques'.", file=sys.stderr)
        return 1

    theme = db.query(Theme).filter(Theme.name == nom_theme).first()
    if theme is None:
        print("Thematique inconnue en base : %r" % nom_theme, file=sys.stderr)
        return 1

    articles = articles_de_la_thematique(db, theme.id)
    print("Thematique %r : %d articles dans le corpus." % (nom_theme, len(articles)))
    print()

    noms_recus = []
    comptes_rendus = []
    for entree in entrees:
        nom = (entree.get("nom") or "").strip()
        mots_cles = [str(m).strip() for m in (entree.get("mots_cles") or []) if str(m).strip()]
        if not nom or not mots_cles:
            print("  IGNOREE (nom ou mots-cles absents) : %r" % entree, file=sys.stderr)
            continue
        noms_recus.append(nom)

        sous_theme = (
            db.query(Subtheme).filter(Subtheme.theme_id == theme.id, Subtheme.name == nom).first()
        )
        if sous_theme is None:
            sous_theme = Subtheme(theme_id=theme.id, name=nom, keywords=mots_cles)
            if appliquer:
                db.add(sous_theme)
                db.flush()
            else:
                # En simulation, l'objet n'est pas persisté : on lui donne un
                # identifiant factice pour pouvoir compter sans écrire.
                sous_theme.id = -1
        else:
            sous_theme.keywords = mots_cles

        comptes_rendus.append(rattacher(db, sous_theme, articles, appliquer))

    obsoletes = (
        db.query(Subtheme)
        .filter(Subtheme.theme_id == theme.id, Subtheme.name.notin_(noms_recus))
        .all()
        if noms_recus
        else []
    )

    print("%-38s %8s %9s  %s" % ("SOUS-THEMATIQUE", "NUMEROS", "ARTICLES", "MOTS-CLES STERILES"))
    for cr in sorted(comptes_rendus, key=lambda c: c["articles"], reverse=True):
        steriles = ", ".join(cr["mots_cles_steriles"]) if cr["mots_cles_steriles"] else "-"
        print("%-38s %8d %9d  %s" % (cr["nom"][:38], cr["numeros"], cr["articles"], steriles))

    ids_theme = {mid for mid, _ in articles}
    couverts: set[int] = set()
    for cr in comptes_rendus:
        couverts |= cr["numeros_ids"]
    orphelins = len(ids_theme - couverts)

    print()
    print("Numeros de la thematique  : %d" % len(ids_theme))
    print("Numeros rattaches         : %d" % len(couverts))
    print("Numeros dans « Autres »   : %d" % orphelins)
    if orphelins > len(ids_theme) // 3:
        print("  ATTENTION : plus d'un tiers des numeros n'est rattache a rien.")
        print("  Le decoupage est probablement trop etroit — relancer le modele.")

    if obsoletes:
        print()
        print("Sous-thematiques absentes du fichier (seront supprimees) :")
        for o in obsoletes:
            print("  - %s" % o.name)
        if appliquer:
            for o in obsoletes:
                db.delete(o)

    if appliquer:
        db.commit()
        print()
        print("Applique.")
    else:
        db.rollback()
        print()
        print("SIMULATION — rien n'a ete ecrit. Relancer avec --appliquer pour valider.")
    return 0


def recalculer_tout(db, appliquer: bool) -> int:
    """Rejoue le rattachement de toutes les sous-thematiques deja en base.

    Aucun modele de langage n'intervient : les mots-cles sont conserves avec
    chaque sous-thematique, il suffit de les reconfronter au corpus. C'est ce
    qu'il faut lancer apres l'arrivee de nouveaux numeros.
    """
    sous_themes = db.query(Subtheme).join(Theme).order_by(Theme.name, Subtheme.name).all()
    if not sous_themes:
        print("Aucune sous-thematique en base : rien a recalculer.")
        return 0

    # Le corpus est charge une fois par thematique, pas une fois par
    # sous-thematique : sans ce cache, dix sous-thematiques relisaient dix
    # fois les memes milliers d'articles.
    corpus: dict[int, list[tuple[int, str]]] = {}

    print("%-24s %-30s %8s %9s" % ("THEMATIQUE", "SOUS-THEMATIQUE", "NUMEROS", "ARTICLES"))
    for sous_theme in sous_themes:
        if sous_theme.theme_id not in corpus:
            corpus[sous_theme.theme_id] = articles_de_la_thematique(db, sous_theme.theme_id)
        cr = rattacher(db, sous_theme, corpus[sous_theme.theme_id], appliquer)
        print(
            "%-24s %-30s %8d %9d"
            % (sous_theme.theme.name[:24], cr["nom"][:30], cr["numeros"], cr["articles"])
        )

    if appliquer:
        db.commit()
        print()
        print("Applique.")
    else:
        db.rollback()
        print()
        print("SIMULATION — rien n'a ete ecrit. Relancer avec --appliquer.")
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("-f", "--fichier", help="JSON produit par le modele de langage")
    parseur.add_argument(
        "--recalculer-tout",
        action="store_true",
        help="rejouer le rattachement de toutes les sous-thematiques existantes",
    )
    parseur.add_argument(
        "--appliquer",
        action="store_true",
        help="ecrire reellement en base (par defaut : simulation)",
    )
    args = parseur.parse_args()

    if not args.fichier and not args.recalculer_tout:
        parseur.error("indiquer --fichier ou --recalculer-tout")

    db = SessionLocal()
    try:
        if args.recalculer_tout:
            return recalculer_tout(db, args.appliquer)
        return importer_fichier(db, Path(args.fichier), args.appliquer)
    except Exception:
        # Une transaction laissee ouverte apres une erreur bloquerait les
        # connexions suivantes du pool.
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
