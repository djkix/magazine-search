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


def extract_pages(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    try:
        for page_number, page in enumerate(doc, start=1):
            rect = page.rect
            raw_text = page.get_text("text")
            words_raw = page.get_text("words")  # x0, y0, x1, y1, word, block_no, line_no, word_no
            words = [
                {
                    "text": w[4],
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
