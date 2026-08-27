import logging
import traceback
from pathlib import Path

from sqlalchemy import func

from app.config import get_settings
from app.database import SessionLocal
from app.models import Article, Magazine, OcrStatus, Page, PageLanguage, ScanStatus
from app.services.meili import ensure_index_configured, index_page
from app.services.toc import extract_toc
from app.worker.ocr import detect_language, ensure_text_layer, extract_pages, render_cover_thumbnail

logger = logging.getLogger("worker.tasks")
settings = get_settings()


def _refresh_table_of_contents(db, magazine: Magazine, last_page_number: int) -> None:
    """Best-effort: a failure here must not mark the whole magazine as failed."""
    try:
        magazine.toc_status = OcrStatus.processing
        db.commit()

        pages = db.query(Page).filter(Page.magazine_id == magazine.id).order_by(Page.page_number).all()
        entries = sorted(extract_toc(magazine, pages), key=lambda e: e["start_page"])

        db.query(Article).filter(Article.magazine_id == magazine.id).delete()
        for i, entry in enumerate(entries):
            next_start = entries[i + 1]["start_page"] if i + 1 < len(entries) else last_page_number + 1
            end_page = max(entry["start_page"], next_start - 1)
            db.add(
                Article(
                    magazine_id=magazine.id,
                    title=entry["title"],
                    start_page=entry["start_page"],
                    end_page=end_page,
                )
            )

        magazine.toc_status = OcrStatus.done
        magazine.toc_error_message = None
        db.commit()
    except Exception as exc:  # noqa: BLE001 - non-fatal, reported on the magazine row
        db.rollback()
        magazine = db.get(Magazine, magazine.id)
        if magazine is not None:
            magazine.toc_status = OcrStatus.failed
            magazine.toc_error_message = str(exc)
            db.commit()
        logger.exception("TOC extraction failed for magazine %s", magazine.id)


def process_magazine(magazine_id: int) -> None:
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is None:
            logger.warning("Magazine %s not found, skipping", magazine_id)
            return

        magazine.scan_status = ScanStatus.processing
        db.commit()

        source_path = Path(settings.nas_mount_path) / magazine.file_path

        processed_dir = Path(settings.processed_dir)
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_path = processed_dir / f"{magazine.id}.pdf"
        ensure_text_layer(source_path, processed_path)

        cover_dir = Path(settings.covers_dir)
        cover_dir.mkdir(parents=True, exist_ok=True)
        cover_path = cover_dir / f"{magazine.id}.png"
        render_cover_thumbnail(processed_path, cover_path)
        magazine.cover_thumbnail_path = str(cover_path)

        ensure_index_configured()

        last_page_number = 0
        for page_data in extract_pages(processed_path):
            lang = detect_language(page_data["raw_text"])
            page = (
                db.query(Page)
                .filter(Page.magazine_id == magazine.id, Page.page_number == page_data["page_number"])
                .first()
            )
            if page is None:
                page = Page(magazine_id=magazine.id, page_number=page_data["page_number"])
                db.add(page)

            page.raw_text = page_data["raw_text"]
            page.words = page_data["words"]
            page.language = PageLanguage(lang) if lang else None
            page.ocr_status = OcrStatus.done
            page.error_message = None
            db.flush()

            index_page(page, magazine)
            last_page_number = max(last_page_number, page_data["page_number"])

        magazine.scan_status = ScanStatus.done
        magazine.error_message = None
        db.commit()
        logger.info("Magazine %s processed successfully", magazine_id)

        _refresh_table_of_contents(db, magazine, last_page_number)
    except Exception as exc:  # noqa: BLE001 - failure is reported on the magazine row, not re-raised silently
        db.rollback()
        magazine = db.get(Magazine, magazine_id)
        if magazine is not None:
            magazine.scan_status = ScanStatus.failed
            magazine.error_message = f"{exc}\n{traceback.format_exc()[-2000:]}"
            db.commit()
        logger.exception("Failed to process magazine %s", magazine_id)
        raise
    finally:
        db.close()


def retry_toc(magazine_id: int) -> None:
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is None:
            logger.warning("Magazine %s not found, skipping TOC retry", magazine_id)
            return
        last_page_number = db.query(func.max(Page.page_number)).filter(Page.magazine_id == magazine_id).scalar() or 0
        _refresh_table_of_contents(db, magazine, last_page_number)
    finally:
        db.close()
