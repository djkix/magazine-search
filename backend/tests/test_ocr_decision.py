"""Décision OCR : le point aveugle le plus coûteux du projet.

Ces deux fonctions déterminent si un document part en OCR forcé, en OCR
partiel, ou pas du tout. Une régression n'y lève aucune exception : elle
produit une bibliothèque indexée sur du texte illisible, ou fait retraiter
inutilement des milliers de pages. Le défaut ne se voit qu'à la recherche,
longtemps après.

Les PDF témoins sont fabriqués à l'exécution avec PyMuPDF plutôt que commités
en binaire : le contenu reste lisible dans le test, et les seuils testés sont
explicites.

Seuils du code au moment de l'écriture :
    MIN_NATIVE_TEXT_CHARS ........... 20 caractères par page
    MIN_PAGE_TOKENS_TO_JUDGE ........ 15 jetons pour qu'une page soit jugeable
    GARBLED_PAGE_COMMON_WORD_RATIO .. 10 % de mots courants
    MIN_GARBLED_PAGES ............... 3 pages corrompues minimum
    MIN_GARBLED_PAGE_FRACTION ....... 5 % des pages jugées
"""

import fitz
import pytest

from app.worker.ocr import (
    MIN_NATIVE_TEXT_CHARS,
    _native_text_is_garbled,
    all_pages_have_native_text,
    get_page_count,
)

# 20 jetons, dont 14 mots courants (70 %) : de la prose normale.
PROSE = "le chat de la maison est sur le toit avec un chien et des amis dans le jardin pour que"

# 18 jetons, aucun mot courant (0 %) : ce que produit une police au mapping
# corrompu — du texte non vide, mais dépourvu de tout mot réel.
CHARABIA = "lll why ill xxx qqq zzz mmm ppp vvv nnn bbb ccc ddd fff ggg hhh jjj kkk"

# 5 jetons : trop peu pour être jugée, la page doit être ignorée.
TROP_COURT = "lll why ill xxx qqq"


def _fabriquer_pdf(chemin, pages):
    """pages : liste de chaînes (une par page). None = page vide."""
    doc = fitz.open()
    for contenu in pages:
        page = doc.new_page()
        if contenu:
            # fontsize réduite : à la taille par défaut, une ligne de 85
            # caractères frôle la largeur de page et risquerait de déborder,
            # rendant l'extraction dépendante de la mise en page.
            page.insert_text((50, 72), contenu, fontsize=8)
    doc.save(str(chemin))
    doc.close()
    return chemin


@pytest.fixture
def pdf(tmp_path):
    compteur = {"n": 0}

    def _creer(pages):
        compteur["n"] += 1
        return _fabriquer_pdf(tmp_path / f"test-{compteur['n']}.pdf", pages)

    return _creer


# ---- Présence d'une couche de texte ----


def test_document_de_prose_a_du_texte_natif(pdf):
    assert all_pages_have_native_text(pdf([PROSE, PROSE, PROSE])) is True


def test_page_vide_invalide_tout_le_document(pdf):
    """Une seule page sans texte suffit : le document doit passer par l'OCR."""
    assert all_pages_have_native_text(pdf([PROSE, None, PROSE])) is False


def test_document_entierement_scanne(pdf):
    assert all_pages_have_native_text(pdf([None, None])) is False


def test_page_juste_sous_le_seuil_de_caracteres(pdf):
    """Le seuil est un minimum inclusif : en dessous, la page ne compte pas."""
    court = "a" * (MIN_NATIVE_TEXT_CHARS - 1)
    assert all_pages_have_native_text(pdf([court])) is False


# ---- Détection de texte corrompu ----


def test_prose_normale_non_signalee(pdf):
    """Le faux positif est le risque principal : signaler à tort déclenche un
    --force-ocr inutile sur tout le document."""
    assert _native_text_is_garbled(pdf([PROSE] * 10)) is False


def test_document_massivement_corrompu(pdf):
    assert _native_text_is_garbled(pdf([CHARABIA] * 10)) is True


def test_trois_pages_corrompues_suffisent(pdf):
    """3 pages corrompues sur 8 jugées : au-dessus des deux seuils."""
    assert _native_text_is_garbled(pdf([CHARABIA] * 3 + [PROSE] * 5)) is True


def test_deux_pages_corrompues_ne_suffisent_pas(pdf):
    """MIN_GARBLED_PAGES protège contre une page de crédits ou une publicité
    pleine page qui ferait basculer tout un document à tort."""
    assert _native_text_is_garbled(pdf([CHARABIA] * 2 + [PROSE] * 5)) is False


def test_pages_trop_courtes_ignorees(pdf):
    """Aucune page jugeable : le document ne doit pas être déclaré corrompu
    par défaut."""
    assert _native_text_is_garbled(pdf([TROP_COURT] * 10)) is False


def test_document_vide_non_signale(pdf):
    """Pas de texte du tout : c'est le rôle de all_pages_have_native_text,
    pas celui de la détection de corruption."""
    assert _native_text_is_garbled(pdf([None, None, None])) is False


# ---- Cohérence des deux décisions ----


def test_le_charabia_passe_le_test_de_presence_mais_pas_celui_de_qualite(pdf):
    """C'est exactement le cas que la détection existe pour rattraper : du
    texte bien présent, donc --skip-text laisserait les pages en l'état, alors
    qu'elles sont inexploitables."""
    document = pdf([CHARABIA] * 5)

    assert all_pages_have_native_text(document) is True
    assert _native_text_is_garbled(document) is True


# ---- Comptage de pages ----


def test_comptage_des_pages(pdf):
    assert get_page_count(pdf([PROSE] * 7)) == 7
