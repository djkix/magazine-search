"""Faux positifs d'extraction de sommaire.

Calcul pur : aucune base, aucun PDF (l'extraction est appelée sans
`pdf_path`, donc sans PyMuPDF).

Les textes ci-dessous sont ceux, **authentiques**, des pages 4 à 6 de
« What Hi Fi n°263 » tels que l'OCR les a produits. Ce numéro ne figurait pas
parmi les 767 « sans sommaire » : il comptait comme réussi, avec deux entrées
inventées — page 200 et page 500. Un faux succès, plus insidieux qu'un échec
franc puisque rien ne le signale.

Deux défauts distincts s'y cumulaient :

1. « SOMMAIRE » apparaissant en pages 4 ET 5, la page 6 — le premier article —
   était analysée elle aussi, car la page suivante était ajoutée sans
   condition. Sa prose a fourni « 200 W RMS, une réponse de 25 Hz… ».
2. Le motif « nombre + majuscule » acceptait « 500 DR : un combo légendaire »,
   fin de « Naim NAC 552/NAP 500 DR » coupée par un retour à la ligne.
"""

from app.models import Page
from app.services.sommaire_ocr import (
    _find_boilerplate_templates,
    _find_sommaire_pages,
    extract_articles_from_ocr,
)

PAGE_4 = """JUILLET/AOÛT 2026 |
SOMMAIRE
VTT
LE NOUVEAU
VISAGE DES
PROJECTEURS
4 modéles qui rendent
la projection aussi
accessible que
"""

PAGE_5 = """LES TEMPS FORTS
28
Cambridge Audio
L/RS : tout vient à
point à qui sait
attendre
62
4 amplis pour donner
un nouveau souffle à
votre systme
78
The Watt/Puppy
de Wilson Audio :
la résurrection!
86
Naim NAC 552/NAP
500 DR: un combo
légendaire
SOMMAIRE
92
Classiques et nouveautés
du moment : notre sélection
JUILLET/AOÛT 2026 5
"""

# Premier article du numéro : de la prose, pas un sommaire.
PAGE_6 = """JUILLET/AOÛT 2026
LA LEGACY GARDE
LA TETE HAUTE
La Legacy 3230 première du nom occupait déjà le sommet de la gamme colonnes
sa réputation.Impossible de manquer son trait de caractère : une sphère en résine
La fiche annonce une puissance admissible de
200 W RMS, une réponse de 25 Hz à 30 kHz et une sensibilité de 91 dB. Attention
à l'amplificateur : l'impédance nominale de 4 ohms chute à 2,9 ohms vers 103 Hz
comme la bi-amplification.Reste un gabarit de fleuron : 1350 mm de haut
"""

NOMBRE_DE_PAGES = 130


def _page(numero, texte=""):
    p = Page()
    p.page_number = numero
    p.raw_text = texte
    return p


def _numero_complet():
    """Le numéro entier : pages 4 à 6 réelles, le reste vide.

    Le nombre total de pages compte : c'est lui qui rend « page 200 »
    manifestement impossible.
    """
    pages = []
    for n in range(1, NOMBRE_DE_PAGES + 1):
        texte = {4: PAGE_4, 5: PAGE_5, 6: PAGE_6}.get(n, "")
        pages.append(_page(n, texte))
    return pages


def test_la_page_de_prose_nest_pas_retenue():
    """Le défaut n°1 : la page suivante était ajoutée sans condition."""
    pages = _numero_complet()
    trouvees = _find_sommaire_pages(pages, _find_boilerplate_templates(pages))

    assert 5 in trouvees, "la vraie page de sommaire doit être retenue"
    assert 6 not in trouvees, "la page d'article ne doit plus être analysée"


def test_aucune_entree_au_dela_du_document():
    """Le défaut n°2 : un numéro de page supérieur au nombre de pages est
    forcément faux. C'est ce qui écarte « 500 DR » et « 200 W RMS »."""
    entrees = extract_articles_from_ocr(_numero_complet())

    hors_bornes = [e for e in entrees if e["start_page"] > NOMBRE_DE_PAGES]
    assert hors_bornes == [], f"entrées impossibles conservées : {hors_bornes}"


def test_les_vraies_entrees_sont_extraites():
    """Contrôle inverse : les correctifs ne doivent pas tout filtrer.

    Les numéros 28, 62, 78, 86 et 92 figurent bien dans le texte OCR, chacun
    seul sur sa ligne et suivi de son titre — un format que la machine à
    états sait traiter.
    """
    pages = {e["start_page"] for e in extract_articles_from_ocr(_numero_complet())}

    assert pages, "aucune entrée extraite d'un sommaire pourtant lisible"
    assert pages & {28, 62, 78, 86, 92}, f"aucun numéro attendu retrouvé : {sorted(pages)}"


def test_aucune_entree_negative_ou_nulle():
    for e in extract_articles_from_ocr(_numero_complet()):
        assert e["start_page"] > 0
