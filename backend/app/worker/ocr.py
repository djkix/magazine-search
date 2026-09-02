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


def ensure_text_layer(source_path: Path, output_path: Path) -> None:
    """Write a copy of source_path to output_path with a text layer on every page.

    Pages that already carry a native text layer are left untouched; only pages
    without one are sent through OCR (ocrmypdf's --skip-text does this per page).
    """
    if all_pages_have_native_text(source_path):
        shutil.copyfile(source_path, output_path)
        return

    result = subprocess.run(
        [
            "ocrmypdf",
            "--skip-text",
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


def _blocks_by_column(page: fitz.Page) -> str:
    """Vertical fallback reading order: split blocks into a left/right
    column by x-position and read each column fully top-to-bottom before
    moving to the next - the natural order for a genuine multi-column
    layout (e.g. two full-height columns), which linear "text" mode can
    scramble by following the PDF's internal content-stream order instead."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    if not blocks:
        return ""
    mid_x = (page.rect.x0 + page.rect.x1) / 2
    left = sorted((b for b in blocks if (b[0] + b[2]) / 2 < mid_x), key=lambda b: b[1])
    right = sorted((b for b in blocks if (b[0] + b[2]) / 2 >= mid_x), key=lambda b: b[1])
    return "\n".join(b[4] for b in [*left, *right])


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
