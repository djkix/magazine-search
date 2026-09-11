#!/usr/bin/env python3
"""Exporte, thématique par thématique, les titres d'articles à soumettre à un
modèle de langage pour en tirer des sous-thématiques.

STRICTEMENT EN LECTURE : ce script n'écrit rien en base.

Pourquoi hors ligne plutôt que dans l'application ? Le quota Gemini est de
20 requêtes par jour. Une requête par thématique consommerait les trois quarts
d'une journée pour une seule passe, et interdirait toute reprise. L'export
permet d'employer un modèle sans contrainte de quota, et surtout de RELIRE le
découpage proposé avant de l'injecter : une sous-thématique mal nommée se
corrige dans un fichier, pas dans une table.

UN FICHIER PAR THÉMATIQUE, volontairement. Le corpus complet représente des
dizaines de milliers de titres, qui ne tiendraient dans aucune invite. Chaque
thématique se traite séparément.

Usage, depuis l'hôte :

    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py --lister
    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py -t "Santé" --stdout
    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py --tout -o /data/exports

--lister affiche le volume de chaque thématique sans rien exporter : c'est par
là qu'il faut commencer, pour repérer celles dont le corpus est trop gros pour
une seule invite.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Article, Magazine, Theme, theme_magazines

# En deçà, une thématique n'a pas de sous-structure exploitable : la
# navigation affiche directement ses numéros. Aligné sur le seuil appliqué
# côté API.
MIN_NUMEROS_POUR_SOUS_THEMATIQUES = 8


def _titres_de_la_thematique(db, theme_id: int) -> list[str]:
    """Titres d'articles des numéros portant cette thématique, dédoublonnés.

    Le dédoublonnage est fait ici plutôt que côté modèle : un même titre
    répété dans quarante numéros n'apporte rien à l'identification des
    regroupements, et gonfle l'invite d'autant.
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


def _inventaire(db) -> list[tuple[int, str, int]]:
    """(id, nom, nombre de numéros) par thématique, la plus fournie d'abord."""
    return (
        db.query(Theme.id, Theme.name, func.count(Magazine.id.distinct()))
        .join(theme_magazines, theme_magazines.c.theme_id == Theme.id)
        .join(Magazine, Magazine.id == theme_magazines.c.magazine_id)
        .group_by(Theme.id, Theme.name)
        .order_by(func.count(Magazine.id.distinct()).desc(), Theme.name)
        .all()
    )


CONSIGNE = (
    "Regroupe ces titres d'articles en 5 a 12 sous-thematiques concretes. "
    "Reponds UNIQUEMENT par un JSON de la forme "
    '{\"thematique\": \"<nom>\", \"sous_thematiques\": '
    '[{\"nom\": \"...\", \"mots_cles\": [\"...\", \"...\"]}]}. '
    "Les mots-cles doivent etre des expressions REELLEMENT presentes dans les "
    "titres : ils servent a rattacher automatiquement les numeros, un mot-cle "
    "absent du corpus ne rattachera rien."
)


def _charge_utile(db, theme_id: int, nom: str, numeros: int, max_titres: int | None) -> dict:
    titres = _titres_de_la_thematique(db, theme_id)
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


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parseur.add_argument("--lister", action="store_true", help="inventaire des thematiques, sans export")
    parseur.add_argument("-t", "--thematique", help="exporter cette seule thematique (nom exact)")
    parseur.add_argument("--tout", action="store_true", help="exporter toutes les thematiques eligibles")
    parseur.add_argument("--stdout", action="store_true", help="afficher au lieu d'ecrire un fichier")
    parseur.add_argument("-o", "--sortie", default="/data/exports", help="repertoire de sortie")
    parseur.add_argument(
        "--max-titres",
        type=int,
        default=None,
        help="plafonne le nombre de titres par thematique (defaut : aucun plafond)",
    )
    args = parseur.parse_args()

    db = SessionLocal()
    try:
        inventaire = _inventaire(db)

        if args.lister or not (args.thematique or args.tout):
            print("%-32s %8s %9s" % ("THEMATIQUE", "NUMEROS", "TITRES"))
            for theme_id, nom, numeros in inventaire:
                titres = len(_titres_de_la_thematique(db, theme_id))
                marque = "" if numeros >= MIN_NUMEROS_POUR_SOUS_THEMATIQUES else "  (sous le seuil)"
                print("%-32s %8d %9d%s" % (nom[:32], numeros, titres, marque))
            print()
            print("Seuil de sous-thematisation : %d numeros." % MIN_NUMEROS_POUR_SOUS_THEMATIQUES)
            print("Au-dela de ~2000 titres, prevoir de decouper l'invite.")
            return 0

        if args.thematique:
            cibles = [(i, n, c) for i, n, c in inventaire if n == args.thematique]
            if not cibles:
                print("Thematique introuvable : %r" % args.thematique, file=sys.stderr)
                print("Noms disponibles : %s" % ", ".join(n for _, n, _ in inventaire), file=sys.stderr)
                return 1
        else:
            cibles = [(i, n, c) for i, n, c in inventaire if c >= MIN_NUMEROS_POUR_SOUS_THEMATIQUES]

        if args.stdout:
            if len(cibles) != 1:
                print("--stdout exige une thematique unique (-t).", file=sys.stderr)
                return 1
            theme_id, nom, numeros = cibles[0]
            charge = _charge_utile(db, theme_id, nom, numeros, args.max_titres)
            print(json.dumps(charge, ensure_ascii=False, indent=2))
            return 0

        repertoire = Path(args.sortie)
        repertoire.mkdir(parents=True, exist_ok=True)
        for theme_id, nom, numeros in cibles:
            charge = _charge_utile(db, theme_id, nom, numeros, args.max_titres)
            # Nom de fichier assaini : les thematiques peuvent contenir des
            # espaces, des accents ou une barre oblique.
            sur = "".join(c if c.isalnum() else "_" for c in nom).strip("_")
            chemin = repertoire / ("thematique_%s.json" % sur)
            chemin.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                "%-32s %5d numeros %6d titres -> %s"
                % (nom[:32], numeros, charge["titres_total"], chemin)
            )
        print()
        print("Recuperer les fichiers depuis l'hote :")
        print("  docker cp <conteneur>:%s ./exports" % repertoire)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
