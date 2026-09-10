"""Détection de la page de sommaire.

Calcul pur : aucune base, aucun PDF. Les objets `Page` sont instanciés sans
session, seuls `page_number` et `raw_text` étant lus par le code testé.

Ces cas viennent de la bibliothèque réelle. Le plus important est
`cm/contenis` : Computer Music intitule ses rubriques « cm/contents », et
l'OCR y lit un « i » à la place du « t ». Deux obstacles cumulés que la
détection stricte ne pouvait pas franchir, et qui expliquaient à eux seuls
une centaine de numéros sans sommaire.
"""

import pytest

from app.models import Page
from app.services.sommaire_ocr import (
    MIN_NOMBRES_POUR_SOMMAIRE,
    _compter_nombres_isoles,
    _find_sommaire_pages,
    _is_sommaire_heading,
    _mot_de_titre_approchant,
)


def page(numero, texte):
    p = Page()
    p.page_number = numero
    p.raw_text = texte
    return p


# ---- Reconnaissance tolérante du mot ----


@pytest.mark.parametrize(
    "ligne",
    [
        "Sommaire",
        "SOMMAIRE",
        "Contents",
        "cm/contents",  # préfixe de marque
        "cm/contenis",  # + lettre abîmée par l'OCR : le cas réel
        "CM/CONTENTS",
        "Index",
        "S O M M A I R E",  # composition lettrée, recollée en amont
    ],
)
def test_titres_reconnus(ligne):
    assert _mot_de_titre_approchant(ligne) is True


@pytest.mark.parametrize(
    "ligne",
    [
        "cm/inbox",  # autre rubrique du même magazine
        "Reviews",
        "",
        "sommaire",  # minuscule initiale : ligne de prose, pas un titre
        "Une ligne beaucoup trop longue pour être un titre de rubrique",
    ],
)
def test_titres_rejetes(ligne):
    assert _mot_de_titre_approchant(ligne) is False


def test_la_version_stricte_reste_stricte():
    """`_is_sommaire_heading` ne doit PAS être assouplie : elle sert de
    référence sur la fenêtre large des 30 premières pages, où un faux
    positif serait coûteux. La tolérance est réservée au repli guidé."""
    assert _is_sommaire_heading("Sommaire") is True
    assert _is_sommaire_heading("cm/contenis") is False


# ---- Comptage des numéros isolés ----


def test_comptage_des_numeros_isoles():
    lignes = ["Titre", "42", "Autre titre", "7", "pas un nombre 12", "108"]
    assert _compter_nombres_isoles(lignes) == 3


# ---- Détection au niveau de la page ----


SOMMAIRE_REALISTE = "\n".join(
    ["ISSUE 181 SEPTEMBER 2012", "cm/contenis", "Stereo Width", "18",
     "Producer Masterclass", "24", "The cm Interview", "32"]
)


def test_page_avec_titre_approchant_et_numeros():
    pages = [page(1, "Couverture"), page(4, SOMMAIRE_REALISTE), page(5, "Article")]

    assert 4 in _find_sommaire_pages(pages, set())


def test_le_mot_seul_ne_suffit_pas():
    """Garde-fou central : sans pagination, une page portant le mot n'est
    pas retenue. C'est ce qui empêche une publicité ou une page d'ours de
    passer pour un sommaire, la reconnaissance du mot étant volontairement
    permissive."""
    sans_numeros = "cm/contenis\nUn paragraphe de texte sans la moindre pagination."
    pages = [page(4, sans_numeros)]

    assert _find_sommaire_pages(pages, set()) == set()


def test_les_numeros_seuls_ne_suffisent_pas():
    """Sans mot évocateur, le repli guidé ne se déclenche pas.

    Volontairement trois numéros et non quatre : à partir de quatre lignes
    de forme « entrée », c'est le repli par densité — antérieur et distinct —
    qui prendrait le relais, et le test ne dirait plus rien du chemin visé.
    """
    que_des_numeros = "\n".join(["Publicité", "19", "99", "45"])
    pages = [page(4, que_des_numeros)]

    assert _find_sommaire_pages(pages, set()) == set()


def test_seuil_de_numeros_respecte():
    trop_peu = "cm/contenis\nTitre\n18\nAutre\n24"
    assert _compter_nombres_isoles(trop_peu.splitlines()) < MIN_NOMBRES_POUR_SOMMAIRE
    assert _find_sommaire_pages([page(4, trop_peu)], set()) == set()


def test_repli_limite_aux_premieres_pages():
    """Un « index » en fin de numéro ne doit pas être pris pour un sommaire."""
    pages = [page(150, SOMMAIRE_REALISTE)]

    assert _find_sommaire_pages(pages, set()) == set()


def test_la_detection_stricte_reste_prioritaire():
    """Quand un vrai titre existe, c'est lui qui décide — le repli guidé ne
    doit pas s'y substituer ni élargir la sélection."""
    pages = [page(3, "Sommaire\nTitre\n12\nAutre\n18\nEncore\n24"),
             page(6, SOMMAIRE_REALISTE)]
    trouvees = _find_sommaire_pages(pages, set())

    assert 3 in trouvees
    assert 6 not in trouvees
