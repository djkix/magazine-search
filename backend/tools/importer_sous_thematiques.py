#!/usr/bin/env python3
"""Injecte les sous-thématiques produites hors ligne, en ligne de commande.

EN SIMULATION PAR DÉFAUT : sans --appliquer, rien n'est écrit.

Ce script n'est qu'une mise en forme pour le terminal. Toute la logique vit
dans app/services/import_sous_thematiques.py, partagée avec l'API
d'administration — le dépôt de fichier depuis le tableau de bord produit donc
exactement le même résultat.

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

    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py -f /data/exports/sante.json
    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py -f ... --appliquer
    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py --recalculer-tout --appliquer

--recalculer-tout rejoue le rattachement des sous-thématiques déjà en base,
sans fichier ni modèle : c'est ce qu'il faut lancer après l'arrivée de
nouveaux numéros.
"""

import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.import_sous_thematiques import ImportInvalide, importer, recalculer_tout


def _afficher_import(rapport: dict) -> None:
    print("Thematique %r : %d articles dans le corpus." % (rapport["thematique"], rapport["articles_corpus"]))
    print()
    print("%-38s %8s %9s  %s" % ("SOUS-THEMATIQUE", "NUMEROS", "ARTICLES", "MOTS-CLES STERILES"))
    for st in rapport["sous_thematiques"]:
        steriles = ", ".join(st["mots_cles_steriles"]) if st["mots_cles_steriles"] else "-"
        print("%-38s %8d %9d  %s" % (st["nom"][:38], st["numeros"], st["articles"], steriles))

    if rapport["entrees_ignorees"]:
        print()
        print("Entrees ignorees (nom ou mots-cles absents) :")
        for e in rapport["entrees_ignorees"]:
            print("  - %s" % e)

    print()
    print("Numeros de la thematique  : %d" % rapport["numeros_thematique"])
    print("Numeros rattaches         : %d" % rapport["numeros_rattaches"])
    print("Numeros dans « Autres »   : %d" % rapport["numeros_autres"])
    if rapport["decoupage_suspect"]:
        print("  ATTENTION : plus d'un tiers des numeros n'est rattache a rien.")
        print("  Le decoupage est probablement trop etroit — relancer le modele.")

    if rapport["obsoletes"]:
        print()
        print("Sous-thematiques absentes du fichier (supprimees) :")
        for nom in rapport["obsoletes"]:
            print("  - %s" % nom)


def _afficher_recalcul(rapport: dict) -> None:
    if not rapport["sous_thematiques"]:
        print("Aucune sous-thematique en base : rien a recalculer.")
        return
    print("%-24s %-30s %8s %9s" % ("THEMATIQUE", "SOUS-THEMATIQUE", "NUMEROS", "ARTICLES"))
    for st in rapport["sous_thematiques"]:
        print(
            "%-24s %-30s %8d %9d"
            % (st["thematique"][:24], st["nom"][:30], st["numeros"], st["articles"])
        )


def _epilogue(applique: bool) -> None:
    print()
    if applique:
        print("Applique.")
    else:
        print("SIMULATION — rien n'a ete ecrit. Relancer avec --appliquer pour valider.")


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
        "--appliquer", action="store_true", help="ecrire reellement (par defaut : simulation)"
    )
    args = parseur.parse_args()

    if not args.fichier and not args.recalculer_tout:
        parseur.error("indiquer --fichier ou --recalculer-tout")

    db = SessionLocal()
    try:
        if args.recalculer_tout:
            rapport = recalculer_tout(db, args.appliquer)
            _afficher_recalcul(rapport)
            _epilogue(rapport["applique"])
            return 0

        try:
            charge = json.loads(Path(args.fichier).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("Fichier illisible : %s" % exc, file=sys.stderr)
            return 1

        try:
            rapport = importer(db, charge, args.appliquer)
        except ImportInvalide as exc:
            print(str(exc), file=sys.stderr)
            return 1

        _afficher_import(rapport)
        _epilogue(rapport["applique"])
        return 0
    except Exception:
        # Une transaction laissee ouverte apres une erreur bloquerait les
        # connexions suivantes du pool.
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
