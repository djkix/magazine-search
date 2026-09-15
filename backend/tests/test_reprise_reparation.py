"""Chaîne de reprise après échec d'ocrmypdf.

Aucun binaire n'est lancé : qpdf, Ghostscript et ocrmypdf sont remplacés par
des bouchons. Ce qui est vérifié ici, c'est l'enchaînement des recours et le
message d'erreur final, pas le comportement des outils eux-mêmes.

Contexte : deux pannes distinctes ont été mesurées sur le corpus.

- « Systeme D 870 » : index des objets cassé, Ghostscript refuse d'ouvrir le
  document. qpdf le répare.
- « Systeme D 859 » : le document s'ouvre, mais le rendu casse page 121 sur
  une géométrie incohérente (`img2pdf.NegativeDimensionError`). qpdf recopie
  la géométrie fautive et ne change rien ; seule une réécriture Ghostscript
  débloque le cas.

La chaîne devait donc passer d'un recours à deux.
"""

import subprocess

import pytest

from app.worker import ocr


def _ocrmypdf_factice(code: int, stderr: str = ""):
    """Bouchon de `_lancer_ocrmypdf` rendant toujours le même code."""

    def _lancer(source_path, output_path, mode):
        return subprocess.CompletedProcess(args=[], returncode=code, stderr=stderr)

    return _lancer


@pytest.fixture
def chemins(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    return source, tmp_path / "sortie.pdf"


def test_le_succes_qpdf_arrete_la_chaine(monkeypatch, chemins):
    """Ghostscript est coûteux : on ne l'appelle pas si qpdf a suffi."""
    source, sortie = chemins
    appels = []

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", lambda s, d: appels.append("qpdf") or True)
    monkeypatch.setattr(
        ocr, "_normaliser_avec_ghostscript", lambda s, d: appels.append("gs") or True
    )
    monkeypatch.setattr(ocr, "_lancer_ocrmypdf", _ocrmypdf_factice(0))

    ocr._reprendre_apres_reparation(source, sortie, 2, "erreur initiale")

    assert appels == ["qpdf"]


def test_ghostscript_est_tente_quand_qpdf_ne_debloque_rien(monkeypatch, chemins):
    """Le cas « Systeme D 859 » : qpdf réussit, mais l'OCR échoue quand même."""
    source, sortie = chemins
    appels = []
    codes = iter([15, 0])  # echec apres qpdf, succes apres Ghostscript

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", lambda s, d: appels.append("qpdf") or True)
    monkeypatch.setattr(
        ocr, "_normaliser_avec_ghostscript", lambda s, d: appels.append("gs") or True
    )
    monkeypatch.setattr(
        ocr,
        "_lancer_ocrmypdf",
        lambda s, o, m: subprocess.CompletedProcess(args=[], returncode=next(codes), stderr=""),
    )

    ocr._reprendre_apres_reparation(source, sortie, 15, "NegativeDimensionError")

    assert appels == ["qpdf", "gs"]


def test_ghostscript_est_tente_meme_si_qpdf_est_absent(monkeypatch, chemins):
    """qpdf indisponible ne doit pas court-circuiter le recours suivant."""
    source, sortie = chemins
    appels = []

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", lambda s, d: appels.append("qpdf") or False)
    monkeypatch.setattr(
        ocr, "_normaliser_avec_ghostscript", lambda s, d: appels.append("gs") or True
    )
    monkeypatch.setattr(ocr, "_lancer_ocrmypdf", _ocrmypdf_factice(0))

    ocr._reprendre_apres_reparation(source, sortie, 7, "erreur initiale")

    assert appels == ["qpdf", "gs"]


def test_le_message_final_nomme_les_recours_tentes(monkeypatch, chemins):
    source, sortie = chemins

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", lambda s, d: True)
    monkeypatch.setattr(ocr, "_normaliser_avec_ghostscript", lambda s, d: True)
    monkeypatch.setattr(ocr, "_lancer_ocrmypdf", _ocrmypdf_factice(7, "Ghostscript rasterizing failed"))

    with pytest.raises(RuntimeError) as echec:
        ocr._reprendre_apres_reparation(source, sortie, 7, "erreur initiale")

    message = str(echec.value)
    assert "qpdf puis ghostscript" in message
    assert "Ghostscript rasterizing failed" in message


def test_aucune_reparation_possible_conserve_l_erreur_d_origine(monkeypatch, chemins):
    """Sans recours applicable, c'est la cause initiale qui doit remonter."""
    source, sortie = chemins

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", lambda s, d: False)
    monkeypatch.setattr(ocr, "_normaliser_avec_ghostscript", lambda s, d: False)
    monkeypatch.setattr(ocr, "_lancer_ocrmypdf", _ocrmypdf_factice(0))

    with pytest.raises(RuntimeError) as echec:
        ocr._reprendre_apres_reparation(source, sortie, 7, "Input file is encrypted")

    message = str(echec.value)
    assert "aucune réparation n'a abouti" in message
    assert "Input file is encrypted" in message


def test_les_copies_reparees_sont_supprimees(monkeypatch, chemins):
    """Une copie réparée pèse autant que la source : elle ne doit pas rester."""
    source, sortie = chemins

    def _reparer(source_path, destination):
        destination.write_bytes(b"%PDF-1.4\n")
        return True

    monkeypatch.setattr(ocr, "_reparer_avec_qpdf", _reparer)
    monkeypatch.setattr(ocr, "_normaliser_avec_ghostscript", _reparer)
    monkeypatch.setattr(ocr, "_lancer_ocrmypdf", _ocrmypdf_factice(7))

    with pytest.raises(RuntimeError):
        ocr._reprendre_apres_reparation(source, sortie, 7, "erreur initiale")

    restants = [c.name for c in sortie.parent.glob("*-repare.pdf")]
    assert restants == []


def test_normalisation_rejetee_si_des_pages_disparaissent(monkeypatch, tmp_path):
    """Garde-fou : Ghostscript peut rendre 0 en ayant abandonné des pages.

    Remplacer un document abîmé par un document tronqué serait pire que
    l'échec qu'on essaie de rattraper.
    """
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    destination = tmp_path / "normalise.pdf"

    def _gs(*args, **kwargs):
        destination.write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(args=[], returncode=0, stderr="")

    monkeypatch.setattr(ocr.subprocess, "run", _gs)
    # 132 pages en entree, 130 en sortie : deux pages perdues en silence.
    monkeypatch.setattr(ocr, "_compter_pages", lambda chemin: 132 if chemin == source else 130)

    assert ocr._normaliser_avec_ghostscript(source, destination) is False


def test_normalisation_acceptee_si_le_compte_de_pages_tient(monkeypatch, tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    destination = tmp_path / "normalise.pdf"

    def _gs(*args, **kwargs):
        destination.write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(args=[], returncode=0, stderr="")

    monkeypatch.setattr(ocr.subprocess, "run", _gs)
    monkeypatch.setattr(ocr, "_compter_pages", lambda chemin: 132)

    assert ocr._normaliser_avec_ghostscript(source, destination) is True


def test_ghostscript_absent_ne_fait_pas_planter(monkeypatch, tmp_path):
    """L'image pourrait ne pas embarquer gs : le recours doit juste être sauté."""
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    def _absent(*args, **kwargs):
        raise FileNotFoundError("gs")

    monkeypatch.setattr(ocr.subprocess, "run", _absent)

    assert ocr._normaliser_avec_ghostscript(source, tmp_path / "sortie.pdf") is False
