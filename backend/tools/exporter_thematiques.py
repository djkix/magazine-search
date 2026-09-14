#!/usr/bin/env python3
"""Exporte le corpus complet des titres d'articles, a soumettre a un modele de
langage pour en tirer la taxonomie a deux niveaux.

STRICTEMENT EN LECTURE : ce script n'ecrit rien en base.

Pourquoi hors ligne ? Le quota Gemini de l'application est de 20 requetes par
jour. Classer 13 500 articles par l'API prendrait des semaines. L'export
permet d'employer un modele sans contrainte de quota, et surtout de RELIRE la
taxonomie proposee avant de l'injecter : un regroupement mal nomme se corrige
dans un fichier, pas dans une table.

UN SEUL FICHIER, GROUPE PAR COLLECTION. Un decoupage par collection traitee
separement ferait diverger la taxonomie — une revue rendant « Alimentation >
budget », une autre « Budget > alimentation », sans rien pour les reconcilier.
En une passe, le modele voit tout.

Usage, depuis l'hote :

    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py --resume
    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py --stdout > corpus.json
    docker exec magazine-search-app-backend-1 python tools/exporter_thematiques.py -o /data/exports

--resume affiche la volumetrie sans rien exporter : c'est par la qu'il faut
commencer, pour savoir si le corpus tient dans une seule invite.
"""

import argparse
import json
from pathlib import Path

from app.database import SessionLocal
from app.services.export_thematiques import charge_utile, nom_de_fichier, resume

# Au-dela, le corpus ne tiendra pas dans l'invite de la plupart des modeles et
# il faudra le livrer en plusieurs fois. L'import etant cumulatif, c'est
# possible sans rien perdre.
SEUIL_CARACTERES_UNE_INVITE = 600_000


def main() -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("--resume", action="store_true", help="volumetrie seule, sans export")
    parseur.add_argument("--stdout", action="store_true", help="afficher au lieu d'ecrire un fichier")
    parseur.add_argument("-o", "--sortie", default="/data/exports", help="repertoire de sortie")
    args = parseur.parse_args()

    db = SessionLocal()
    try:
        if args.resume:
            infos = resume(db)
            print("Articles    : %d" % infos["articles"])
            print("Collections : %d (celles sans article sont omises)" % infos["collections"])
            return 0

        charge = charge_utile(db)
        caracteres = charge["caracteres_titres"]

        if args.stdout:
            print(json.dumps(charge, ensure_ascii=False, indent=2))
            return 0

        repertoire = Path(args.sortie)
        repertoire.mkdir(parents=True, exist_ok=True)
        chemin = repertoire / nom_de_fichier()
        chemin.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding="utf-8")

        print("%d collections, %d titres uniques, %d caracteres" % (
            charge["collections_exportees"], charge["titres_uniques"], caracteres
        ))
        print("-> %s" % chemin)
        if caracteres > SEUIL_CARACTERES_UNE_INVITE:
            print()
            print("Le corpus depasse %d caracteres : prevoir de le livrer au modele" % SEUIL_CARACTERES_UNE_INVITE)
            print("en plusieurs fois. L'import est cumulatif, rien ne sera perdu.")
        print()
        print("Recuperer le fichier depuis l'hote :")
        print("  docker cp <conteneur>:%s ." % chemin)
        print()
        print("Ou, plus simple, le telecharger depuis le tableau de bord.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
