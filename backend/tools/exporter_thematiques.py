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

from app.database import SessionLocal
from app.services.export_thematiques import (
    MIN_NUMEROS_POUR_SOUS_THEMATIQUES,
    charge_utile,
    inventaire,
    nom_de_fichier,
    titres_de_la_thematique,
)


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
        thematiques = inventaire(db)

        if args.lister or not (args.thematique or args.tout):
            print("%-32s %8s %9s" % ("THEMATIQUE", "NUMEROS", "TITRES"))
            for theme_id, nom, numeros in thematiques:
                titres = len(titres_de_la_thematique(db, theme_id))
                marque = "" if numeros >= MIN_NUMEROS_POUR_SOUS_THEMATIQUES else "  (sous le seuil)"
                print("%-32s %8d %9d%s" % (nom[:32], numeros, titres, marque))
            print()
            print("Seuil de sous-thematisation : %d numeros." % MIN_NUMEROS_POUR_SOUS_THEMATIQUES)
            print("Au-dela de ~2000 titres, prevoir de decouper l'invite.")
            return 0

        if args.thematique:
            cibles = [(i, n, c) for i, n, c in thematiques if n == args.thematique]
            if not cibles:
                print("Thematique introuvable : %r" % args.thematique, file=sys.stderr)
                print("Noms disponibles : %s" % ", ".join(n for _, n, _ in thematiques), file=sys.stderr)
                return 1
        else:
            cibles = [(i, n, c) for i, n, c in thematiques if c >= MIN_NUMEROS_POUR_SOUS_THEMATIQUES]

        if args.stdout:
            if len(cibles) != 1:
                print("--stdout exige une thematique unique (-t).", file=sys.stderr)
                return 1
            theme_id, nom, numeros = cibles[0]
            charge = charge_utile(db, theme_id, nom, numeros, args.max_titres)
            print(json.dumps(charge, ensure_ascii=False, indent=2))
            return 0

        repertoire = Path(args.sortie)
        repertoire.mkdir(parents=True, exist_ok=True)
        for theme_id, nom, numeros in cibles:
            charge = charge_utile(db, theme_id, nom, numeros, args.max_titres)
            # Nom de fichier assaini : les thematiques peuvent contenir des
            # espaces, des accents ou une barre oblique.
            chemin = repertoire / nom_de_fichier(nom)
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
