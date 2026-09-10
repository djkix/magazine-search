"""Extraction des entrées d'une page de sommaire.

Calcul pur : aucune base, aucun PDF.

Le texte ci-dessous est celui, **authentique**, de la page 5 de « Systeme D
Bricothemes n°50 » tel que l'OCR l'a produit — reproduit verbatim, sauts de
ligne compris. C'est ce corpus réel qui a révélé le défaut : la page était
correctement détectée, les titres et numéros parfaitement lisibles, et
pourtant aucune entrée n'en était tirée sur 71 numéros de cette collection.

La cause tenait à un caractère. Le motif attendait « 42 Titre » — numéro,
espaces, majuscule — alors que Système D compose « 100 /  La rénovation ».
La barre oblique faisait échouer la ligne entière.
"""

from app.services.sommaire_ocr import _LEADING_INLINE_RE, _parse_entries

# Verbatim, y compris les espaces en fin de ligne et les apostrophes typographiques.
PAGE_SYSTEME_D = """/ 5
RÉALISATIONS RÉUSSIES
100 /  La rénovation d'une toiture  
en lauzes
106 /  La transformation 
d’une longère bretonne
112 /  La reconstruction d’une maison 
en Lozère 
116 /  Un abri de jardin bien isolé 
ALLER PLUS LOIN
118 /  Astuces et bons plans
120 /  En librairie et sur Internet
122 /  Carnet d’adresses
Sommaire
"""


def test_sommaire_systeme_d_reel():
    """Le cas qui a motivé le correctif, sur la donnée d'origine."""
    entrees = _parse_entries(PAGE_SYSTEME_D, set())
    pages = {e["start_page"] for e in entrees}

    assert entrees, "aucune entrée extraite d'un sommaire pourtant lisible"
    assert {100, 106, 112, 116, 118, 120, 122} <= pages


def test_les_titres_sont_repris():
    entrees = {e["start_page"]: e["title"] for e in _parse_entries(PAGE_SYSTEME_D, set())}

    assert "Astuces" in entrees[118]
    assert "Carnet" in entrees[122]


def test_le_folio_nest_pas_une_entree():
    """« / 5 » en tête de page est le numéro de folio, pas un article."""
    pages = {e["start_page"] for e in _parse_entries(PAGE_SYSTEME_D, set())}

    assert 5 not in pages


# ---- Le motif lui-même ----


def test_separateur_barre_oblique_accepte():
    m = _LEADING_INLINE_RE.match("100 /  La rénovation d'une toiture")

    assert m is not None
    assert m.group("page") == "100"
    assert m.group("title").startswith("La rénovation")


def test_separation_par_espace_toujours_acceptee():
    """La forme historique ne doit pas régresser."""
    m = _LEADING_INLINE_RE.match("42 Le titre classique")

    assert m is not None
    assert m.group("page") == "42"


def test_une_vraie_separation_reste_exigee():
    """Sans espace ni séparateur, ce n'est pas une entrée de sommaire."""
    assert _LEADING_INLINE_RE.match("100La rénovation") is None


def test_prose_en_minuscule_rejetee():
    """« 10 questions à se poser » est une accroche, pas une entrée : le
    titre doit commencer par une majuscule."""
    assert _LEADING_INLINE_RE.match("10 questions à se poser") is None


def test_annee_rejetee():
    """Quatre chiffres ne peuvent pas être un numéro de page."""
    assert _LEADING_INLINE_RE.match("2022 Octobre") is None


def test_folio_sans_titre_rejete():
    assert _LEADING_INLINE_RE.match("6 /") is None
