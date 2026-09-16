#!/usr/bin/env python3
"""Réencode en WebP les vignettes de couverture déjà produites en PNG.

Pourquoi : sur une photo de couverture, le PNG est un format sans perte et
pèse 5 à 10 fois plus lourd qu'un WebP visuellement identique à la taille
d'affichage (600 px de large). La page bibliothèque affiche des centaines de
vignettes d'un coup : c'est là son principal coût de chargement.

Le traitement de chaque numéro produit désormais directement du WebP. Ce
script ne sert qu'à rattraper l'existant, sans relancer d'OCR — une
régénération complète coûterait des heures pour un résultat identique.

PRUDENCE : par défaut le script ne fait que mesurer. Il faut `--appliquer`
pour qu'il écrive quoi que ce soit. L'ancien PNG n'est supprimé qu'une fois
le WebP écrit ET le chemin mis à jour en base, jamais avant.

Usage, depuis l'hôte :

    docker exec magazine-search-app-backend-1 python tools/regenerer_couvertures.py
    docker exec magazine-search-app-backend-1 python tools/regenerer_couvertures.py --appliquer
"""

import argparse
import sys
from pathlib import Path

# Le paquet `app` vit un cran au-dessus de tools/ dans l'image.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Magazine  # noqa: E402
from app.worker.ocr import render_cover_thumbnail  # noqa: E402

settings = get_settings()


def _source_pdf(magazine: Magazine) -> Path | None:
    """PDF depuis lequel rendre la couverture.

    On préfère la version traitée (celle qui a servi à produire la vignette
    d'origine), et on retombe sur le fichier du NAS si elle a été purgée. La
    première page est la même dans les deux cas.
    """
    traite = Path(settings.processed_dir) / f"{magazine.id}.pdf"
    if traite.exists():
        return traite
    source = Path(settings.nas_mount_path) / magazine.file_path
    return source if source.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--appliquer",
        action="store_true",
        help="écrit réellement les WebP et met la base à jour (sinon, simple mesure)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        magazines = (
            db.query(Magazine)
            .filter(Magazine.cover_thumbnail_path.isnot(None))
            .order_by(Magazine.id)
            .all()
        )

        a_convertir = []
        for magazine in magazines:
            ancien = Path(magazine.cover_thumbnail_path)
            if ancien.suffix.lower() == ".webp":
                continue
            if not ancien.exists():
                continue
            a_convertir.append((magazine, ancien))

        print(f"{len(magazines)} vignette(s) référencée(s), {len(a_convertir)} à convertir")
        if not a_convertir:
            return 0

        poids_avant = poids_apres = 0
        convertis = echecs = 0

        for magazine, ancien in a_convertir:
            pdf = _source_pdf(magazine)
            if pdf is None:
                print(f"  [{magazine.id}] PDF introuvable, ignoré")
                echecs += 1
                continue

            nouveau = ancien.with_suffix(".webp")
            try:
                if args.appliquer:
                    render_cover_thumbnail(pdf, nouveau)
                    magazine.cover_thumbnail_path = str(nouveau)
                    db.commit()
                    # Seulement maintenant : si l'ecriture ou le commit avait
                    # echoue, supprimer le PNG aurait laisse le numero sans
                    # aucune vignette.
                    ancien.unlink(missing_ok=True)
                    poids_apres += nouveau.stat().st_size
                else:
                    # En simulation on encode dans un fichier temporaire pour
                    # mesurer le gain reel, puis on l'efface aussitot.
                    temoin = nouveau.with_suffix(".webp.temoin")
                    render_cover_thumbnail(pdf, temoin)
                    poids_apres += temoin.stat().st_size
                    temoin.unlink(missing_ok=True)

                poids_avant += ancien.stat().st_size if ancien.exists() else 0
                convertis += 1
            except Exception as exc:  # noqa: BLE001 - on continue le lot
                db.rollback()
                print(f"  [{magazine.id}] échec : {exc}")
                echecs += 1

            if convertis and convertis % 100 == 0:
                print(f"  ... {convertis} traitée(s)")

        mo = 1024 * 1024
        print()
        print(f"converties : {convertis}    échecs : {echecs}")
        if poids_avant:
            print(f"avant : {poids_avant / mo:.1f} Mo    après : {poids_apres / mo:.1f} Mo")
            print(f"gain  : {100 * (1 - poids_apres / poids_avant):.1f} %")
        if not args.appliquer:
            print()
            print("SIMULATION — relancer avec --appliquer pour écrire.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
