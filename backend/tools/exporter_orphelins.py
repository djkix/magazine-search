#!/usr/bin/env python3
"""Exporte les articles qu'aucune sous-thematique n'attrape, avec la taxonomie
deja en place, pour la faire ETENDRE par un modele de langage.

STRICTEMENT EN LECTURE : ce script n'ecrit rien en base.

Difference avec exporter_thematiques.py, qui sort la bibliotheque entiere pour
construire une taxonomie de zero : ici on ne sort que ce qui reste a classer.
Soumettre les 13 500 titres pour n'obtenir que des ajouts noie le signal et
consomme du contexte pour rien.

Le fichier embarque sa propre consigne. Le modele recoit donc les regles avec
les donnees, au lieu d'un prompt colle a part qu'on finit par oublier de
mettre a jour.

POURQUOI CA COMPTE POUR LA SUITE. Les nouveaux numeros sont rattaches
automatiquement aux sous-thematiques existantes, par simple correspondance de
mots-cles, sans aucun appel externe. Enrichir la taxonomie n'est donc pas un
rattrapage ponctuel : c'est ce qui determine la qualite du classement des
numeros a venir.

Usage, depuis l'hote :

    docker exec magazine-search-app-backend-1 python tools/exporter_orphelins.py --resume
    docker exec magazine-search-app-backend-1 python tools/exporter_orphelins.py --stdout > orphelins.json
    docker exec magazine-search-app-backend-1 python tools/exporter_orphelins.py -o /data/exports

Commencer par --resume : il dit si le fichier tient dans une seule invite.
"""

import argparse
import json
import sys
from pathlib import Path

# Le paquet `app` vit un cran au-dessus de tools/ dans l'image.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services.export_orphelins import charge_utile, nom_de_fichier, resume  # noqa: E402

# Au-dela, le fichier ne tiendra pas dans l'invite de la plupart des modeles.
# L'import etant cumulatif, le livrer en plusieurs fois ne perd rien.
SEUIL_CARACTERES_UNE_INVITE = 600_000


def main() -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("--resume", action="store_true", help="volumetrie seule, sans export")
    parseur.add_argument(
        "--stdout", action="store_true", help="afficher au lieu d'ecrire un fichier"
    )
    parseur.add_argument("-o", "--sortie", default="/data/exports", help="repertoire de sortie")
    args = parseur.parse_args()

    db = SessionLocal()
    try:
        infos = resume(db)
        if args.resume:
            print("Articles au total   : %d" % infos["articles_total"])
            print("Non rattaches       : %d" % infos["articles_orphelins"])
            print("Titres uniques      : %d (doublons retires)" % infos["titres_uniques"])
            print("Collections         : %d" % infos["collections"])
            print("Caracteres de titre : %d" % infos["caracteres_titres"])
            if infos["caracteres_titres"] > SEUIL_CARACTERES_UNE_INVITE:
                print()
                print("ATTENTION : au-dela de %d caracteres, prevoir" % SEUIL_CARACTERES_UNE_INVITE)
                print("plusieurs envois. L'import est cumulatif, rien ne sera perdu.")
            return 0

        if infos["articles_orphelins"] == 0:
            print("Aucun article orphelin : la taxonomie couvre toute la bibliotheque.")
            return 0

        charge = charge_utile(db)
        texte = json.dumps(charge, ensure_ascii=False, indent=2)

        if args.stdout:
            print(texte)
            return 0

        repertoire = Path(args.sortie)
        repertoire.mkdir(parents=True, exist_ok=True)
        chemin = repertoire / nom_de_fichier()
        chemin.write_text(texte, encoding="utf-8")

        print("Ecrit : %s" % chemin)
        print("  %d titres uniques, %d caracteres" % (infos["titres_uniques"], infos["caracteres_titres"]))
        if infos["caracteres_titres"] > SEUIL_CARACTERES_UNE_INVITE:
            print("  ATTENTION : prevoir plusieurs envois, l'import est cumulatif.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
