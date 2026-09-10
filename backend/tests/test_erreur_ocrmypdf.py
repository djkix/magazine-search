"""Résumé des erreurs d'ocrmypdf.

Calcul pur : aucune base, aucun sous-processus.

L'échantillon ci-dessous reproduit la structure réelle d'une sortie d'erreur
observée sur « Systeme D 873 » : la cause utile en tête, noyée sous des
dizaines d'avertissements Tesseract émis une fois par page.

Conserver les 2000 derniers caractères — le comportement précédent — revenait
à garder le bruit et à jeter l'explication. Le message stocké en base
commençait par « tics - possibly poor OCR », une tranche prise au milieu d'un
mot, au milieu des avertissements.
"""

from app.worker.ocr import MAX_LIGNES_ERREUR_OCR, resumer_erreur_ocrmypdf

CAUSE = "Output file: The generated PDF is INVALID"

BRUIT_TESSERACT = "\n".join(
    f"  {page} [tesseract] lots of diacritics - possibly poor OCR" for page in range(10, 40)
)

STDERR_REEL = (
    "Some pages "
    "without filtering to avoid data loss\n"
    f"{CAUSE}\n"
    f"{BRUIT_TESSERACT}\n"
    "  27 [tesseract] Image too small to scale!! (2x36 vs min width of 3)\n"
    "  27 [tesseract] Line cannot be recognized!!\n"
)


def test_la_cause_reelle_est_conservee():
    """Le cas qui a motivé le correctif."""
    resume = resumer_erreur_ocrmypdf(STDERR_REEL)

    assert CAUSE in resume


def test_le_bruit_tesseract_est_ecarte():
    resume = resumer_erreur_ocrmypdf(STDERR_REEL)

    assert "[tesseract]" not in resume
    assert "diacritics" not in resume


def test_le_resume_reste_court():
    """Un message destiné à l'affichage, pas un dump de 2000 caractères."""
    resume = resumer_erreur_ocrmypdf(STDERR_REEL)

    assert len(resume.split(" | ")) <= MAX_LIGNES_ERREUR_OCR


def test_repli_si_tout_est_du_bruit():
    """Si la sortie ne contient que des avertissements, mieux vaut les
    remonter que de ne rien dire du tout."""
    resume = resumer_erreur_ocrmypdf(BRUIT_TESSERACT)

    assert resume
    assert "tesseract" in resume


def test_sortie_vide():
    assert resumer_erreur_ocrmypdf("") == "(aucune sortie d'erreur)"
    assert resumer_erreur_ocrmypdf(None) == "(aucune sortie d'erreur)"


def test_sortie_courte_conservee_telle_quelle():
    assert resumer_erreur_ocrmypdf("Input file is encrypted") == "Input file is encrypted"
