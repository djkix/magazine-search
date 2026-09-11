#!/usr/bin/env python3
"""Diagnostic de l'extraction de sommaire, collection par collection.

STRICTEMENT EN LECTURE : ce script n'écrit rien, ne relance aucun traitement.

Il répond à la seule question qui oriente le correctif : pour un numéro sans
sommaire, est-ce que la page de sommaire n'a pas été TROUVÉE, ou est-ce
qu'elle a été trouvée mais qu'aucune ENTRÉE n'a pu en être tirée ?

  - Page non trouvée   -> le problème est dans la détection (_is_sommaire_heading,
                          _find_sommaire_pages) : titre absent, écrit autrement,
                          ou sommaire situé au-delà de la fenêtre de recherche.
  - Page trouvée, 0 entrée -> le problème est dans les expressions régulières de
                          mise en page (_parse_entries) : format de ligne non
                          reconnu.

Usage, depuis l'hôte :

    docker exec magazine-search-app-backend-1 python tools/diagnostiquer_sommaire.py --collections
    docker exec magazine-search-app-backend-1 python tools/diagnostiquer_sommaire.py -c "Que Choisir"
    docker exec magazine-search-app-backend-1 python tools/diagnostiquer_sommaire.py -c "Que Choisir" -n 2 --texte

L'option --texte affiche le texte OCR brut des premières pages : c'est LUI
qu'il faut me transmettre, pas une capture d'écran. Le parseur ne voit pas la
page, il voit ce texte — et l'écart entre les deux est justement le bug.
"""

import argparse
import sys

from app.database import SessionLocal
from app.models import Article, Collection, Magazine, OcrStatus, Page, ScanStatus
from app.services.sommaire_ocr import (
    MAX_HEADING_SEARCH_PAGE,
    _find_boilerplate_templates,
    _find_sommaire_pages,
    _is_sommaire_heading,
    _parse_entries,
)

LARGEUR = 78


def titre(texte):
    print()
    print("=" * LARGEUR)
    print(texte)
    print("=" * LARGEUR)


def _sans_sommaire(db):
    """Numéros traités n'ayant produit AUCUN article.

    C'est le critère du tableau de bord, et le seul pertinent : un
    `toc_status` à « done » ne garantit pas qu'un article ait été extrait.
    L'immense majorité des cas problématiques sont justement marqués comme
    réussis tout en étant vides — filtrer sur le statut les manquerait tous.
    """
    return db.query(Magazine).filter(
        Magazine.scan_status == ScanStatus.done,
        ~Magazine.id.in_(db.query(Article.magazine_id).distinct()),
    )


def lister_collections(db):
    """Classement des collections par nombre de numéros sans sommaire."""
    titre("Collections, triées par nombre de numéros sans sommaire")

    base = _sans_sommaire(db)
    lignes = []
    for collection in db.query(Collection).order_by(Collection.name).all():
        total = db.query(Magazine).filter(Magazine.collection_id == collection.id).count()
        sans = base.filter(Magazine.collection_id == collection.id).count()
        if sans:
            lignes.append((sans, total, collection.name))

    if not lignes:
        print("Aucune collection concernée : tous les numéros ont un sommaire.")
        return

    lignes.sort(reverse=True)
    print(f"{'sans sommaire':>14} {'total':>7}  collection")
    print("-" * LARGEUR)
    for sans, total, nom in lignes:
        print(f"{sans:>14} {total:>7}  {nom}")

    print()
    print(f"TOTAL sans article : {base.count()}")

    # Répartition par statut : c'est elle qui révèle l'échec silencieux.
    # Un numéro marqué « done » sans le moindre article signifie que
    # l'extraction s'est déclarée réussie tout en ne produisant rien —
    # indiscernable, côté interface, d'un magazine réellement dépourvu de
    # sommaire.
    print()
    print("Répartition par statut d'extraction :")
    for statut in OcrStatus:
        n = base.filter(Magazine.toc_status == statut).count()
        if n:
            marque = "  <-- échec silencieux" if statut == OcrStatus.done else ""
            print(f"  {statut.value:<12} {n}{marque}")

    print()
    print("Le gain est en haut de liste : même titre, même maquette, un seul")
    print("correctif débloque toute la colonne.")


def diagnostiquer(db, nom_collection, nombre, afficher_texte):
    magazines = (
        _sans_sommaire(db)
        .join(Collection, Collection.id == Magazine.collection_id)
        .filter(Collection.name.ilike(f"%{nom_collection}%"))
        .order_by(Magazine.id)
        .limit(nombre)
        .all()
    )

    if not magazines:
        print(f"Aucun numéro sans sommaire pour une collection contenant « {nom_collection} ».")
        return

    for magazine in magazines:
        titre(f"[{magazine.id}] {magazine.title}")
        print(f"statut sommaire : {magazine.toc_status}")
        if magazine.toc_error_message:
            print(f"erreur          : {magazine.toc_error_message}")

        pages = (
            db.query(Page)
            .filter(Page.magazine_id == magazine.id)
            .order_by(Page.page_number)
            .all()
        )
        if not pages:
            print("Aucune page en base : l'OCR n'a rien produit pour ce numéro.")
            continue

        print(f"pages en base   : {len(pages)}")

        boilerplate = _find_boilerplate_templates(pages)
        trouvees = sorted(_find_sommaire_pages(pages, boilerplate))

        # --- Mode d'échec 1 : aucune page identifiée -------------------
        if not trouvees:
            print()
            print(">>> AUCUNE page de sommaire identifiée.")
            print("    Le problème est dans la DÉTECTION, pas dans le parsing.")
            print(f"    (recherche du titre limitée aux {MAX_HEADING_SEARCH_PAGE} premières pages)")
            print()
            print("    Lignes courtes des 12 premières pages, candidates à un titre :")
            for page in pages[:12]:
                for ligne in (page.raw_text or "").splitlines():
                    ligne = ligne.strip()
                    if 3 <= len(ligne) <= 30:
                        marque = "  <-- reconnu" if _is_sommaire_heading(ligne) else ""
                        print(f"      p.{page.page_number:>3} | {ligne}{marque}")
        # --- Mode d'échec 2 : page trouvée, entrées non extraites ------
        else:
            print(f"pages sommaire  : {trouvees}")
            total = 0
            for numero in trouvees:
                page = next((p for p in pages if p.page_number == numero), None)
                if page is None:
                    continue
                entrees = _parse_entries(page.raw_text or "", boilerplate)
                total += len(entrees)
                print(f"  page {numero:>3} : {len(entrees)} entrée(s)")
                for e in entrees[:5]:
                    print(f"      p.{e.get('start_page')} — {e.get('title')}")
            if total == 0:
                print()
                print(">>> Page trouvée mais AUCUNE entrée extraite.")
                print("    Le problème est dans les EXPRESSIONS RÉGULIÈRES de mise en page.")

        # --- Texte brut, à me transmettre ------------------------------
        if afficher_texte:
            cibles = trouvees or [p.page_number for p in pages[:4]]
            for numero in sorted(cibles)[:4]:
                page = next((p for p in pages if p.page_number == numero), None)
                if page is None:
                    continue
                print()
                print(f"--- texte OCR brut, page {numero} " + "-" * 40)
                print((page.raw_text or "(vide)")[:2500])


def main():
    parseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parseur.add_argument("--collections", action="store_true", help="Lister les collections concernées et sortir")
    parseur.add_argument("-c", "--collection", help="Nom (ou fragment) de la collection à diagnostiquer")
    parseur.add_argument("-n", "--nombre", type=int, default=3, help="Nombre de numéros à examiner (défaut : 3)")
    parseur.add_argument("--texte", action="store_true", help="Afficher le texte OCR brut des pages concernées")
    args = parseur.parse_args()

    db = SessionLocal()
    try:
        if args.collections or not args.collection:
            lister_collections(db)
            if not args.collection:
                print()
                print("Puis : python tools/diagnostiquer_sommaire.py -c \"<nom>\" --texte")
                return 0
        diagnostiquer(db, args.collection, args.nombre, args.texte)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
