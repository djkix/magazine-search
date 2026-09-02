import re
import shutil
import subprocess
from pathlib import Path

import fitz  # PyMuPDF
from langdetect import DetectorFactory, LangDetectException, detect_langs

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

    result = subprocess.run(
        [
            "ocrmypdf",
            "--force-ocr" if garbled else "--skip-text",
            "--language",
            "fra+eng",
            "--output-type",
            "pdf",
            "--optimize",
            "0",
            str(source_path),
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ocrmypdf failed (code {result.returncode}): {result.stderr[-2000:]}")


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
        zoom = max_width / page.rect.width
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
