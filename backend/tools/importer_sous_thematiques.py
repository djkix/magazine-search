#!/usr/bin/env python3
"""Injecte la taxonomie produite hors ligne, en ligne de commande.

EN SIMULATION PAR DEFAUT : sans --appliquer, rien n'est ecrit.

Ce script n'est qu'une mise en forme pour le terminal. Toute la logique vit
dans app/services/import_sous_thematiques.py, partagee avec l'API
d'administration — le depot de fichier depuis le tableau de bord produit donc
exactement le meme resultat.

Deux niveaux, rattaches aux ARTICLES :

    Thematique (Alimentation) -> Sous-thematique (legumes) -> Articles

Format attendu (ce que doit produire le modele) :

    {
      "thematiques": [
        {
          "nom": "Alimentation",
          "sous_thematiques": [
            {"nom": "Legumes", "mots_cles": ["legume", "potager", "maraicher"]},
            {"nom": "Budget alimentaire", "mots_cles": ["panier", "prix alimentaires"]}
          ]
        }
      ]
    }

L'import est CUMULATIF : les sous-thematiques absentes du fichier ne sont pas
supprimees. Un envoi en plusieurs morceaux enrichit la taxonomie au lieu de
l'ecraser, ce qui permet de decouper la reponse du modele quand elle depasse
sa limite de sortie.

Usage, depuis l'hote :

    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py -f /data/exports/taxonomie.json
    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py -f ... --appliquer
    docker exec magazine-search-app-backend-1 python tools/importer_sous_thematiques.py --recalculer-tout --appliquer

--recalculer-tout rejoue le rattachement des sous-thematiques deja en base,
sans fichier ni modele : c'est ce qu'il faut lancer apres l'arrivee de
nouveaux numeros, pour que leurs articles rejoignent les regroupements
existants.
"""

import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.import_sous_thematiques import ImportInvalide, importer, recalculer_tout


def _afficher_couverture(rapport: dict) -> None:
    corpus = rapport["articles_corpus"]
    couverts = rapport["articles_couverts"]
    part = (100.0 * couverts / corpus) if corpus else 0.0
    print()
    print("Articles du corpus        : %d" % corpus)
    print("Articles rattaches        : %d (%.1f %%)" % (couverts, part))
    print("Articles sans rattachement: %d" % rapport["articles_sans_sous_thematique"])
    if corpus and part < 50:
        print()
        print("  ATTENTION : moins de la moitie du corpus est rattachee.")
        print("  Les mots-cles sont probablement trop etroits, ou trop peu nombreux.")


def _afficher_import(rapport: dict) -> None:
    print(
        "%d thematique(s), %d sous-thematique(s)."
        % (rapport["thematiques"], len(rapport["sous_thematiques"]))
    )
    print()
    print(
        "%-22s %-30s %9s  %s"
        % ("THEMATIQUE", "SOUS-THEMATIQUE", "ARTICLES", "MOTS-CLES STERILES")
    )
    for st in rapport["sous_thematiques"]:
        steriles = ", ".join(st["mots_cles_steriles"]) if st["mots_cles_steriles"] else "-"
        print(
            "%-22s %-30s %9d  %s"
            % (st["thematique"][:22], st["nom"][:30], st["articles"], steriles)
        )

    if rapport["entrees_ignorees"]:
        print()
        print("Entrees ignorees (nom ou mots-cles absents) :")
        for e in rapport["entrees_ignorees"]:
            print("  - %s" % e)

    _afficher_couverture(rapport)


def _afficher_recalcul(rapport: dict) -> None:
    if not rapport["sous_thematiques"]:
        print("Aucune sous-thematique en base : rien a recalculer.")
        return
    print("%-22s %-30s %9s" % ("THEMATIQUE", "SOUS-THEMATIQUE", "ARTICLES"))
    for st in rapport["sous_thematiques"]:
        print("%-22s %-30s %9d" % (st["thematique"][:22], st["nom"][:30], st["articles"]))
    _afficher_couverture(rapport)


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
