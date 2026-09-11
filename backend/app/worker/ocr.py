import logging
import re
import shutil
import subprocess
from pathlib import Path

import fitz  # PyMuPDF
from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("worker.ocr")

DetectorFactory.seed = 0  # deterministic langdetect results

MIN_NATIVE_TEXT_CHARS = 20
MIN_TEXT_CHARS_FOR_LANG_DETECT = 20
MIXED_LANGUAGE_PROB_THRESHOLD = 0.3


def all_pages_have_native_text(pdf_path: Path) -> bool:
    doc = fitz.open(pdf_path)
    try:
        return all(len(page.get_text("text").strip()) >= MIN_NATIVE_TEXT_CHARS for page in doc)
    finally:
        doc.close()


# A handful of extremely common, unambiguous French/English words - real
# prose of any length is dense with these; a systematic glyph-to-Unicode
# mismatch (see _native_text_is_garbled) can't coincidentally reproduce
# them, since every occurrence of a given real word is remapped to the
# same wrong output every time, never back to the word itself.
_COMMON_WORDS = {
    "le", "la", "les", "de", "des", "un", "une", "et", "à", "dans", "pour",
    "que", "qui", "est", "sur", "avec", "par", "ce", "en", "au", "aux",
    "the", "and", "of", "to", "in", "for", "is", "on", "with", "by", "at",
    "from", "this", "that", "are", "was",
}
_WORD_RE = re.compile(r"[a-zà-öø-ÿ]{2,}")
MIN_PAGE_TOKENS_TO_JUDGE = 15
GARBLED_PAGE_COMMON_WORD_RATIO = 0.10
MIN_GARBLED_PAGES = 3
MIN_GARBLED_PAGE_FRACTION = 0.05


def _native_text_is_garbled(pdf_path: Path) -> bool:
    """Some PDFs carry non-empty native text that is nevertheless unusable -
    typically a subset/custom font whose glyph-to-Unicode mapping is wrong,
    so PyMuPDF extracts a consistent-looking but meaningless character
    substitution instead of real words (e.g. "lll\\nWhy |\\n| |" instead of
    readable French/English). all_pages_have_native_text can't catch this,
    since the text is non-empty - so this checks instead whether each
    page's text contains a plausible density of the handful of extremely
    common short words every real page of prose is full of, and calls the
    whole document garbled once enough individual pages come up short.

    Judged per page (rather than over one pooled sample) because the
    corruption is typically page/font-specific, not document-wide - some
    pages (covers, full-page ads/images) are also genuinely too short or
    proper-noun-heavy to judge either way, so those are skipped rather than
    counted as evidence in either direction. A handful of low-content pages
    misfiring isn't enough on its own - MIN_GARBLED_PAGES guards against a
    short document (or a couple of legitimately stopword-sparse pages, e.g.
    a credits page) tripping this from one or two false positives."""
    doc = fitz.open(pdf_path)
    try:
        judged = 0
        garbled_pages = 0
        for page in doc:
            tokens = _WORD_RE.findall(page.get_text("text").lower())
            if len(tokens) < MIN_PAGE_TOKENS_TO_JUDGE:
                continue
            judged += 1
            hits = sum(1 for t in tokens if t in _COMMON_WORDS)
            if (hits / len(tokens)) < GARBLED_PAGE_COMMON_WORD_RATIO:
                garbled_pages += 1
        if judged == 0:
            return False
        return garbled_pages >= MIN_GARBLED_PAGES and (garbled_pages / judged) >= MIN_GARBLED_PAGE_FRACTION
    finally:
        doc.close()


def get_page_count(pdf_path: Path) -> int:
    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


# ocrmypdf noie sa sortie d'erreur sous des avertissements Tesseract répétés
# une fois par page — « lots of diacritics - possibly poor OCR », « Image too
# small to scale » — qui n'expliquent rien. Garder la fin brute de stderr
# revenait donc à conserver le bruit et à jeter la ligne utile.
#
# Relevé réel : la cause était « Output file: The generated PDF is INVALID »,
# introuvable dans le message stocké, lequel commençait par « tics - possibly
# poor OCR » — une tranche prise au milieu d'un mot, au milieu du bruit.
_BRUIT_TESSERACT_RE = re.compile(r"^\s*\d+\s*\[tesseract\]", re.IGNORECASE)

# Ghostscript fait suivre son erreur d'un vidage de ses piles internes. Ces
# lignes n'apprennent rien et, sur « Systeme D 870 », occupaient a elles
# seules les cinq lignes conservees : le message stocke se reduisait a
# « Dictionary stack: | --dict:754/1123(ro)(G)-- | ... ».
_BRUIT_GHOSTSCRIPT_RE = re.compile(
    r"^(?:Operand stack:|Execution stack:|Dictionary stack:|Current allocation mode|--\w+[:.]|%\S)",
    re.IGNORECASE,
)

# Lignes qui nomment la panne, ou qu'elles se trouvent dans la sortie. Sans
# elles, « 1 Error: /syntaxerror in --runpdf-- » — la seule ligne utile d'un
# echec Ghostscript — se perd en tete de sortie.
_LIGNE_CAUSE_RE = re.compile(r"(?:error|erreur|exception|unrecoverable|syntaxerror)", re.IGNORECASE)

MAX_LIGNES_ERREUR_OCR = 5


def resumer_erreur_ocrmypdf(stderr: str | None, max_lignes: int = MAX_LIGNES_ERREUR_OCR) -> str:
    """Extrait de la sortie d'erreur d'ocrmypdf les lignes qui expliquent l'échec.

    Écarte d'abord les avertissements par page et les piles Ghostscript, puis
    remonte en tête les lignes qui nomment la panne, où qu'elles soient : selon
    l'outil qui échoue, la cause est en fin de sortie (ocrmypdf) ou tout au
    début (Ghostscript, qui la fait suivre de son vidage de piles). Les
    dernières lignes complètent tant qu'il reste de la place.

    Si tout a été filtré — sortie composée uniquement d'avertissements — on
    retombe sur les lignes brutes plutôt que de ne rien remonter.
    """
    lignes = [ligne.strip() for ligne in (stderr or "").splitlines() if ligne.strip()]
    utiles = [
        ligne
        for ligne in lignes
        if not _BRUIT_TESSERACT_RE.match(ligne) and not _BRUIT_GHOSTSCRIPT_RE.match(ligne)
    ]
    base = utiles or lignes

    retenues = [ligne for ligne in base if _LIGNE_CAUSE_RE.search(ligne)][:max_lignes]
    for ligne in base[-max_lignes:]:
        if len(retenues) >= max_lignes:
            break
        if ligne not in retenues:
            retenues.append(ligne)

    return " | ".join(retenues) or "(aucune sortie d'erreur)"


def _lancer_ocrmypdf(source_path: Path, output_path: Path, mode: str) -> subprocess.CompletedProcess:
    """Un passage d'ocrmypdf. `mode` vaut « --skip-text » ou « --force-ocr »."""
    try:
        return subprocess.run(
            [
                "ocrmypdf",
                mode,
                "--language",
                "fra+eng",
                "--output-type",
                "pdf",
                "--optimize",
                "0",
                str(source_path),
                str(output_path),
            ],
            # stdout part à la poubelle : il n'est jamais lu, et sur un gros
            # document la sortie de progression était intégralement chargée en
            # mémoire. Seul stderr, utilisé pour le message d'erreur, est
            # conservé.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            # Sans timeout, un PDF pathologique bloque l'unique worker
            # indéfiniment. La borne est tenue sous le job_timeout RQ de 30 min
            # pour que l'échec soit signalé proprement sur le numéro plutôt que
            # par la mort du job.
            timeout=settings.ocr_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ocrmypdf interrompu après {settings.ocr_timeout_seconds} s "
            f"(document trop volumineux ou corrompu)"
        ) from exc


# qpdf rend 0 sans avertissement, 3 avec, 2 en cas d'erreur reelle. Traiter 3
# comme un echec ferait rejeter toutes les reparations reussies : reconstruire
# une table de references croisees produit precisement un avertissement.
QPDF_CODES_SUCCES = (0, 3)


def _reparer_avec_qpdf(source_path: Path, destination: Path) -> bool:
    """Réécrit le PDF via qpdf, qui sait reconstruire une table de références
    croisées cassée. Rend True si le fichier réparé est exploitable.

    La table de références croisées est l'index interne qui donne la position
    de chaque objet dans le fichier. Quand elle est absente ou fausse,
    Ghostscript refuse le document dès l'ouverture (« Error: /syntaxerror in
    --runpdf-- ») : ni --skip-text ni --force-ocr n'y changent quoi que ce
    soit, puisque les deux passent par le même moteur. qpdf, lui, retrouve les
    objets en balayant le fichier et réécrit un index correct.

    La source n'est jamais modifiée : la copie réparée est écrite ailleurs.

    Cas réel : « Systeme D - 870 - 07-2018.pdf », dont l'index annonçait un
    objet à l'octet 92770382 sans rien y trouver.
    """
    try:
        resultat = subprocess.run(
            ["qpdf", str(source_path), str(destination)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=settings.ocr_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        logger.warning("qpdf n'a pas terminé dans le délai imparti pour %s", source_path.name)
        return False
    except FileNotFoundError:
        logger.warning("qpdf est absent de l'image : réparation impossible pour %s", source_path.name)
        return False

    if resultat.returncode not in QPDF_CODES_SUCCES:
        logger.warning(
            "qpdf n'a pas pu réparer %s (code %s) : %s",
            source_path.name,
            resultat.returncode,
            resumer_erreur_ocrmypdf(resultat.stderr),
        )
        return False

    return destination.exists() and destination.stat().st_size > 0


def _reprendre_apres_reparation(
    source_path: Path, output_path: Path, code_echec: int, erreur: str
) -> None:
    """Dernier recours : réparer la structure du PDF, puis relancer l'OCR.

    Changer de mode ne sert à rien quand c'est l'index des objets qui est
    cassé : --skip-text et --force-ocr partagent le moteur qui refuse le
    fichier, et échouent avec le même message. Seule une réécriture préalable
    du document débloque la situation.

    Lève si la réparation est impossible ou si l'OCR échoue encore, en
    conservant dans le message l'erreur d'origine plutôt que celle, moins
    parlante, de la tentative de secours.
    """
    logger.warning(
        "ocrmypdf a échoué en --force-ocr pour %s (%s) — tentative de réparation qpdf",
        source_path.name,
        erreur,
    )

    repare = output_path.with_name(f"{output_path.stem}.qpdf-repare.pdf")
    try:
        if not _reparer_avec_qpdf(source_path, repare):
            raise RuntimeError(
                f"ocrmypdf failed (code {code_echec}) y compris en --force-ocr : {erreur}"
            )

        resultat = _lancer_ocrmypdf(repare, output_path, "--force-ocr")
        if resultat.returncode != 0:
            raise RuntimeError(
                f"ocrmypdf failed (code {resultat.returncode}) y compris après réparation qpdf : "
                f"{resumer_erreur_ocrmypdf(resultat.stderr)}"
            )
        logger.info("Document récupéré par la réparation qpdf : %s", source_path.name)
    finally:
        # La copie réparée peut peser autant que la source : on ne la laisse
        # pas s'accumuler dans le dossier des documents traités.
        repare.unlink(missing_ok=True)


def ensure_text_layer(source_path: Path, output_path: Path) -> None:
    """Write a copy of source_path to output_path with a text layer on every page.

    Pages that already carry a native text layer are left untouched; only pages
    without one are sent through OCR (ocrmypdf's --skip-text does this per page).

    A document whose native text is garbled (see _native_text_is_garbled)
    needs a different flag even where text is technically present:
    --skip-text would leave those pages untouched too, since ocrmypdf also
    considers them "already have text" - --force-ocr instead rasterizes and
    re-OCRs every page, discarding the bad text. Only checked once per
    document at first processing, so the extra pass's cost is a one-time
    thing, not a recurring one.
    """
    has_native_text = all_pages_have_native_text(source_path)
    garbled = _native_text_is_garbled(source_path)
    if has_native_text and not garbled:
        shutil.copyfile(source_path, output_path)
        return

    mode = "--force-ocr" if garbled else "--skip-text"
    result = _lancer_ocrmypdf(source_path, output_path, mode)
    if result.returncode == 0:
        return

    erreur = resumer_erreur_ocrmypdf(result.stderr)

    # Déjà en --force-ocr : changer de mode n'apporterait rien, mais la
    # réparation de structure reste à tenter — un index d'objets cassé fait
    # échouer ce mode-là aussi.
    if mode == "--force-ocr":
        _reprendre_apres_reparation(source_path, output_path, result.returncode, erreur)
        return

    # Seconde chance en --force-ocr. Par défaut (--skip-text), ocrmypdf
    # RECOPIE les images d'origine dans le fichier produit : une image JPEG
    # corrompue dans la source contamine donc la sortie, et qpdf refuse le
    # résultat. Cas réel : « Pl_DCT::decompress: JPEG data is corrupt » suivi
    # de « Output file: The generated PDF is INVALID ».
    #
    # --force-ocr rastérise chaque page avant de réencoder : l'image n'est
    # plus recopiée mais régénérée depuis son rendu, ce qui peut contourner
    # le flux abîmé. Sans garantie — si le décodage échoue aussi au rendu,
    # la seconde passe échouera pareillement — mais l'essai ne coûte qu'une
    # passe supplémentaire, et uniquement sur un document déjà en échec.
    logger.warning(
        "ocrmypdf a échoué en %s pour %s (%s) — nouvelle tentative en --force-ocr",
        mode,
        source_path.name,
        erreur,
    )
    result = _lancer_ocrmypdf(source_path, output_path, "--force-ocr")
    if result.returncode == 0:
        logger.info("Document récupéré par la reprise en --force-ocr : %s", source_path.name)
        return

    _reprendre_apres_reparation(
        source_path, output_path, result.returncode, resumer_erreur_ocrmypdf(result.stderr)
    )


def _strip_nul(text: str) -> str:
    """A malformed font mapping in the source PDF can make PyMuPDF yield
    literal NUL (0x00) characters, which Postgres text columns reject
    outright - strip them here, once, so every consumer downstream (DB
    writes, language detection, Meilisearch indexing) sees clean text."""
    return text.replace("\x00", "") if "\x00" in text else text


MIN_COLUMN_GAP_POINTS = 60


def _blocks_by_column(page: fitz.Page) -> str:
    """Vertical fallback reading order: read the left column fully
    top-to-bottom, then the right column - the natural order for a
    genuine multi-column layout, which linear "text" mode can scramble by
    following the PDF's internal content-stream order instead.

    Works at word level (grouped back into their original PyMuPDF lines
    via (block_no, line_no)) rather than whole blocks, because some
    two-column sommaires are laid out as a literal two-column table where
    each physical line already contains both columns side by side - e.g.
    "8 conseils ... 36    Les choisir comme un expert ... 54" - which
    PyMuPDF hands back as one block/line, so a block-level left/right
    split can't separate them; the two halves need to be told apart
    within the line itself. A line's words are split at the single
    largest horizontal gap between them when that gap is wide enough
    (MIN_COLUMN_GAP_POINTS) to be a real column gutter rather than
    ordinary word spacing - otherwise the whole line is classified as one
    side by its own position, which is what makes this also work for a
    genuine full-height two-column layout (nothing to split within any
    single line there, just left-block lines and right-block lines)."""
    words = page.get_text("words")
    if not words:
        return ""
    mid_x = (page.rect.x0 + page.rect.x1) / 2

    lines: dict[tuple[int, int], list] = {}
    for w in words:
        lines.setdefault((w[5], w[6]), []).append(w)

    left_lines: list[tuple[float, str]] = []
    right_lines: list[tuple[float, str]] = []
    for line_words in lines.values():
        line_words.sort(key=lambda w: w[0])
        y = min(w[1] for w in line_words)
        gaps = [(line_words[i + 1][0] - line_words[i][2], i) for i in range(len(line_words) - 1)]
        gap, split_at = max(gaps, default=(0, -1))
        if gap >= MIN_COLUMN_GAP_POINTS:
            left_lines.append((y, " ".join(w[4] for w in line_words[: split_at + 1])))
            right_lines.append((y, " ".join(w[4] for w in line_words[split_at + 1 :])))
        elif (line_words[0][0] + line_words[-1][2]) / 2 < mid_x:
            left_lines.append((y, " ".join(w[4] for w in line_words)))
        else:
            right_lines.append((y, " ".join(w[4] for w in line_words)))

    left_lines.sort(key=lambda item: item[0])
    right_lines.sort(key=lambda item: item[0])
    return "\n".join(text for _, text in [*left_lines, *right_lines])


def _blocks_by_row(page: fitz.Page) -> str:
    """Horizontal fallback reading order: group blocks into horizontal
    bands (blocks whose vertical extent overlaps) and read left-to-right
    within each band - suits a page that alternates full-width banners
    with a column pair beneath them, rather than genuine full-height
    columns (where _blocks_by_column fits better)."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    blocks.sort(key=lambda b: b[1])

    bands: list[list] = []
    band_bottom: float | None = None
    for block in blocks:
        y0, y1 = block[1], block[3]
        if band_bottom is not None and y0 < band_bottom:
            bands[-1].append(block)
            band_bottom = max(band_bottom, y1)
        else:
            bands.append([block])
            band_bottom = y1

    lines = []
    for band in bands:
        band.sort(key=lambda b: b[0])
        lines.extend(block[4] for block in band)
    return "\n".join(lines)


def extract_page_text_alternate(pdf_path: Path, page_number: int, strategy: str) -> str | None:
    """Re-extracts a single page's text using an alternate reading-order
    reconstruction ("columns" or "rows"), instead of the default linear
    order - used on demand as a fallback when the default text yielded
    nothing usable from a page already known to be the sommaire (see
    sommaire_ocr.extract_articles_from_ocr). Not used by default: linear
    order is right far more often, and applying a reconstruction
    unconditionally previously regressed pages it wasn't needed for.
    Returns None if the page doesn't exist or the file can't be opened."""
    try:
        doc = fitz.open(pdf_path)
    except Exception:  # noqa: BLE001 - best-effort fallback, never worth crashing the caller
        return None
    try:
        if page_number < 1 or page_number > doc.page_count:
            return None
        page = doc.load_page(page_number - 1)
        text = _blocks_by_column(page) if strategy == "columns" else _blocks_by_row(page)
        return _strip_nul(text)
    finally:
        doc.close()


def extract_pages(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    try:
        for page_number, page in enumerate(doc, start=1):
            rect = page.rect
            raw_text = _strip_nul(page.get_text("text"))
            words_raw = page.get_text("words")  # x0, y0, x1, y1, word, block_no, line_no, word_no
            words = [
                {
                    "text": _strip_nul(w[4]),
                    "x": w[0] / rect.width,
                    "y": w[1] / rect.height,
                    "w": (w[2] - w[0]) / rect.width,
                    "h": (w[3] - w[1]) / rect.height,
                }
                for w in words_raw
            ]
            pages.append({"page_number": page_number, "raw_text": raw_text, "words": words})
        return pages
    finally:
        doc.close()


def render_cover_thumbnail(pdf_path: Path, output_path: Path, max_width: int = 600) -> None:
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(0)
        largeur = page.rect.width
        if largeur <= 0:
            # Page de dimension nulle (PDF malformé) : sans cette garde, la
            # division lève ZeroDivisionError et fait échouer tout le job.
            raise RuntimeError("Première page de dimension nulle, miniature impossible")
        # Plafonné à 1 : au-delà, on rendrait la page plus grande que sa taille
        # native pour la réduire ensuite, sans gain de qualité.
        zoom = min(max_width / largeur, 1.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(str(output_path))
    finally:
        doc.close()


def detect_language(text: str) -> str | None:
    text = text.strip()
    if len(text) < MIN_TEXT_CHARS_FOR_LANG_DETECT:
        return None
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return None
    if not candidates:
        return None

    top = candidates[0]
    if top.lang not in ("fr", "en"):
        return "mixed"
    if (
        len(candidates) > 1
        and candidates[1].lang in ("fr", "en")
        and candidates[1].prob > MIXED_LANGUAGE_PROB_THRESHOLD
    ):
        return "mixed"
    return top.lang
