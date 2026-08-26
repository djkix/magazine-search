import logging
import traceback
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models import Magazine, OcrStatus, Page, PageLanguage, ScanStatus
from app.services.meili import ensure_index_configured, index_page
from app.worker.ocr import detect_language, ensure_text_layer, extract_pages, render_cover_thumbnail

logger = logging.getLogger("worker.tasks")
settings = get_settings()


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

        magazine.scan_status = ScanStatus.done
        magazine.error_message = None
        db.commit()
        logger.info("Magazine %s processed successfully", magazine_id)
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
