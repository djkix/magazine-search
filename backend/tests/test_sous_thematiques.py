"""Correspondance des mots-clés pour le rattachement aux sous-thématiques.

Calcul pur : aucune base, aucun sous-processus.

C'est la seule partie de la fonctionnalité qui décide QUELS numéros
apparaissent sous QUELLE sous-thématique. Un modèle de langage nomme les
regroupements hors ligne, mais le rattachement se joue ici — d'où ces tests.
"""

from app.services.sous_thematiques import (
    compter_par_numero,
    motif_du_mot_cle,
    motifs_des_mots_cles,
    mots_cles_steriles,
    normaliser,
)


def test_normalisation_casse_et_accents():
    assert normaliser("Crème Solaire") == "creme solaire"
    assert normaliser("MÉDICAMENT") == "medicament"


def test_les_bornes_de_mots_evitent_les_faux_positifs():
    """Sans bornes, « UV » correspondrait dans « ouvrir ».

    C'est le piège principal de cette approche : des sigles courts noieraient
    le rattachement sous le bruit, et l'utilisateur verrait des numéros sans
    rapport sous une sous-thématique.
    """
    uv = motif_du_mot_cle("UV")

    assert uv.search(normaliser("Se proteger des rayons UV"))
    assert not uv.search(normaliser("Comment ouvrir un compte"))


def test_le_pluriel_est_tolere():
    """Les titres de presse sont massivement au pluriel.

    Sans cette tolérance, le mot-clé « crème solaire » manquait « Les crèmes
    solaires au banc d'essai » — soit une bonne part du corpus.
    """
    creme = motif_du_mot_cle("crème solaire")

    assert creme.search(normaliser("Une creme solaire efficace"))
    assert creme.search(normaliser("Les cremes solaires au banc d'essai"))
    assert creme.search(normaliser("Les cremes solaire"))


def test_un_mot_tronque_ne_correspond_pas():
    """La tolérance au pluriel ne doit pas ouvrir la porte à n'importe quoi."""
    creme = motif_du_mot_cle("crème solaire")

    assert not creme.search(normaliser("cremerie solaire"))


def test_espaces_multiples_de_l_ocr():
    creme = motif_du_mot_cle("crème solaire")

    assert creme.search(normaliser("creme    solaire bio"))


def test_mot_cle_vide_ignore():
    assert motif_du_mot_cle("   ") is None
    assert motifs_des_mots_cles(["", "  ", "UV"]) != []
    assert len(motifs_des_mots_cles(["", "  ", "UV"])) == 1


def test_comptage_par_numero():
    articles = [
        (1, "Crème solaire : notre test"),
        (1, "Protection solaire pour enfants"),
        (1, "Assurance auto : comparatif"),
        (2, "Les rayons UV en question"),
        (3, "Comment ouvrir un livret A"),
    ]
    motifs = motifs_des_mots_cles(["crème solaire", "protection solaire", "UV"])

    comptes = compter_par_numero(motifs, articles)

    assert comptes[1] == 2
    assert comptes[2] == 1
    # Le numéro 3 ne correspond à rien : il relèvera de « Autres ».
    assert 3 not in comptes


def test_un_article_ne_compte_qu_une_fois():
    """La grandeur mesurée est « combien d'articles parlent de ça ».

    Compter les mots-clés touchés récompenserait les listes verbeuses : une
    sous-thématique à quinze synonymes écraserait les autres au tri.
    """
    articles = [(9, "Crème solaire et protection solaire renforcee")]
    motifs = motifs_des_mots_cles(["crème solaire", "protection solaire"])

    assert compter_par_numero(motifs, articles) == {9: 1}


def test_mots_cles_steriles_signales():
    """Un mot-clé sans correspondance trahit un regroupement inventé.

    Sans cette remontée, la sous-thématique serait vide sans explication, et
    on soupçonnerait le rattachement plutôt que la source.
    """
    titres = ["Crème solaire : notre test", "Assurance auto"]

    steriles = mots_cles_steriles(["crème solaire", "médicament pour dormir"], titres)

    assert steriles == ["médicament pour dormir"]
