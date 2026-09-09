"""Tests du parsing des métadonnées de numéro à partir du nom de fichier.

Aucune infrastructure requise : ces fonctions sont du calcul pur.

Les cas de la première série sont ceux **documentés dans le docstring** de
`parse_issue_metadata` : ils énoncent le contrat voulu par l'auteur, et non
une interprétation de ma part. C'est la zone la plus fragile du projet — une
régression n'y lève aucune exception, elle range simplement les numéros au
mauvais endroit dans la bibliothèque.
"""

import pytest

from app.services.issue_parser import (
    extract_issue_number_from_cover_text,
    extract_year_from_cover_text,
    parse_issue_metadata,
)


@pytest.mark.parametrize(
    ("titre", "numero_attendu", "annee", "mois", "libelle"),
    [
        ("60 Millions De Consommateurs - 580 - 2022-05", "580", 2022, 5, "Mai"),
        ("Ca M'intéresse - 514 - 12-2023", "514", 2023, 12, "Décembre"),
        (
            "AD Architectural Digest France - Septembre-Octobre 2026",
            None,
            2026,
            9,
            "Septembre-Octobre",
        ),
        ("Computer Music 316 January 2023", "316", 2023, 1, "Janvier"),
    ],
)
def test_exemples_documentes(titre, numero_attendu, annee, mois, libelle):
    numero, date, label = parse_issue_metadata(titre)

    assert numero == numero_attendu
    assert date is not None
    assert (date.year, date.month) == (annee, mois)
    assert label == libelle


def test_date_ancre_sur_le_premier_mois_dune_plage():
    """Pour un bimestriel, la date de publication doit pointer sur le premier
    mois : c'est elle qui sert au tri et au filtrage par année."""
    _, date, label = parse_issue_metadata("Revue - Septembre-Octobre 2026")

    assert label == "Septembre-Octobre"
    assert date.month == 9


def test_nom_de_collection_retire_avant_parsing():
    """Une collection dont le nom contient des chiffres ne doit pas voir ce
    nombre pris pour un numéro de parution."""
    numero, _, _ = parse_issue_metadata(
        "60 Millions De Consommateurs - Hors-Série - Impôts",
        collection_name="60 Millions De Consommateurs",
    )

    assert numero != "60"


def test_titre_sans_date_ni_numero():
    numero, date, label = parse_issue_metadata("Magazine Hors-Série - Impôts")

    assert numero is None
    assert date is None
    assert label is None


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Le magazine de l'année 2024, page 3", 2024),
        ("Édition 1998 spéciale", 1998),
        ("Aucune date ici", None),
        ("Numéro 4321 sans année", None),
    ],
)
def test_annee_depuis_le_texte_de_couverture(texte, attendu):
    assert extract_year_from_cover_text(texte) == attendu


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("N° 123 - Janvier", "123"),
        ("n°45", "45"),
        ("N 123 sans le signe degre", None),
        ("Pas de numéro", None),
    ],
)
def test_numero_depuis_le_texte_de_couverture(texte, attendu):
    assert extract_issue_number_from_cover_text(texte) == attendu
