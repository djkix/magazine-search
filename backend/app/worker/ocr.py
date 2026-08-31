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


def _reconstruct_reading_order(page: fitz.Page) -> str:
    """PyMuPDF's raw "text" mode follows the PDF's internal content stream
    order, which for a magazine's side-by-side columns (common in a
    sommaire page, e.g. a full-width section banner followed by a left and
    right column of entries) doesn't reliably match the visual reading
    order - entries can come out missing, merged, or attributed to the
    wrong page number as a result.

    Reconstructed instead from positioned text blocks, grouped into
    horizontal bands (blocks whose vertical extent overlaps) and, within
    each band, ordered left-to-right - approximates "read top-to-bottom,
    left-to-right within a row" the way a person actually reads the page."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    blocks.sort(key=lambda b: b[1])  # top-to-bottom by y0

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
        band.sort(key=lambda b: b[0])  # left-to-right by x0
        lines.extend(block[4] for block in band)
    return "\n".join(lines)


def extract_pages(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    try:
        for page_number, page in enumerate(doc, start=1):
            rect = page.rect
            raw_text = _strip_nul(_reconstruct_reading_order(page))
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
