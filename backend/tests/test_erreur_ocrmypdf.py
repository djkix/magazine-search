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


# Sortie reelle d'un echec Ghostscript, observee sur « Systeme D 870 » : la
# table de references croisees du PDF est cassee, Ghostscript refuse le fichier
# des l'ouverture. Sa cause est en TETE de sortie, suivie d'un vidage de piles
# qui, seul, remplissait les cinq lignes conservees.
STDERR_GHOSTSCRIPT = """   **** Warning: considering '0000000000 XXXXX n' as a free entry.
1 Error: /syntaxerror in --runpdf--
Operand stack:
   --dict:754/1123(ro)(G)--   --dict:0/20(G)--
Execution stack:
   %interp_exit .runexec2 --nostringval-- --nostringval--
Dictionary stack:
   --dict:754/1123(ro)(G)--   --dict:0/20(G)--   --dict:86/200(L)--   --dict:6/10(L)--
Current allocation mode is local
GPL Ghostscript 10.05.1: Unrecoverable error, exit code 1
SubprocessOutputError: Ghostscript rasterizing failed
"""


def test_la_cause_ghostscript_en_tete_est_conservee():
    """La cause d'un echec Ghostscript ouvre la sortie au lieu de la clore.

    Ne garder que les dernieres lignes remontait « Dictionary stack: |
    --dict:754/1123(ro)(G)-- | ... », strictement identique d'un numero a
    l'autre et sans aucune valeur diagnostique.
    """
    resume = resumer_erreur_ocrmypdf(STDERR_GHOSTSCRIPT)

    assert "syntaxerror" in resume


def test_les_piles_ghostscript_sont_ecartees():
    resume = resumer_erreur_ocrmypdf(STDERR_GHOSTSCRIPT)

    assert "Dictionary stack" not in resume
    assert "--dict:" not in resume
    assert len(resume.split(" | ")) <= MAX_LIGNES_ERREUR_OCR
