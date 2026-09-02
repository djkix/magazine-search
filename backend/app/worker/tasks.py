import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from app.config import get_settings
from app.database import SessionLocal
from app.models import Article, Magazine, OcrStatus, Page, PageLanguage, ScanStatus, Theme, theme_magazines
from app.queue import ingestion_queue
from app.services.issue_parser import extract_issue_number_from_cover_text, extract_year_from_cover_text
from app.services.magazine_themes import generate_magazine_themes
from app.services.meili import ensure_index_configured, index_page, index_pages
from app.services.progress import clear_magazine_progress, set_magazine_progress
from app.services.sommaire_ocr import extract_articles_from_ocr
from app.services.theme_batch import assign_themes_batch
from app.worker.ocr import detect_language, ensure_text_layer, extract_pages, get_page_count, render_cover_thumbnail

logger = logging.getLogger("worker.tasks")
settings = get_settings()

# Keeps the batch's combined prompt a reasonable size while still cutting
# Gemini requests roughly by this factor compared to one request per
# magazine - see process_pending_theme_batch.
THEME_BATCH_SIZE = 8


def extract_and_store_articles(db, magazine: Magazine) -> None:
    """Sommaire extraction is fully local (regex over already-OCR'd text,
    see sommaire_ocr.py) - no Gemini call, so it runs synchronously right
    after OCR instead of via an async/batched job. Best-effort: a failure
    here must not mark the whole magazine as failed."""
    try:
        pages = db.query(Page).filter(Page.magazine_id == magazine.id).order_by(Page.page_number).all()
        last_page_number = max((p.page_number for p in pages), default=0)
        processed_path = Path(settings.processed_dir) / f"{magazine.id}.pdf"
        entries = sorted(
            extract_articles_from_ocr(pages, pdf_path=processed_path if processed_path.exists() else None),
            key=lambda e: e["start_page"],
        )

        # Locks the magazine row so a second concurrent call for the same
        # magazine - e.g. the admin "Relancer" button on a full reprocess
        # and the lighter "toc/retry" action both landing close together -
        # waits here instead of interleaving its own delete+insert with
        # this one. Without this, under READ COMMITTED, a concurrent run's
        # DELETE only removes rows already committed at the time it runs,
        # so two overlapping runs each insert their own full set and both
        # end up in the table side by side as duplicates.
        db.query(Magazine).filter(Magazine.id == magazine.id).with_for_update().first()

        db.query(Article).filter(Article.magazine_id == magazine.id).delete()
        for i, entry in enumerate(entries):
            if "end_page" in entry:
                end_page = entry["end_page"]
            else:
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
        logger.exception("Sommaire extraction failed for magazine %s", magazine.id)


def process_pending_theme_batch() -> None:
    """Clusters up to THEME_BATCH_SIZE already-sommaire'd magazines with no
    themes yet into shared themes, in a single Gemini request covering all
    of them (see assign_themes_batch) rather than one request per magazine -
    this is the only remaining Gemini call in the ingestion pipeline now
    that sommaire extraction is done locally.

    Enqueued once after every OCR completion; safe to invoke repeatedly -
    it's a no-op once nothing is pending. During a bulk scan, many of these
    calls pile up in the queue behind the (much slower) process_magazine
    OCR jobs, so by the time the first one actually runs, most or all of
    that batch's magazines already have no themes yet - naturally
    coalescing a large backlog into a handful of requests instead of one
    per magazine.

    Pending is tracked via `themed_at` (set below for every magazine in the
    batch, whether or not Gemini found it a theme) rather than "has no
    theme_magazines row" - a magazine Gemini can't theme (e.g. too few
    articles) would otherwise never get excluded, so it kept being
    resubmitted, and re-billed against the daily quota, every single time
    any other magazine's OCR completed and re-enqueued this job."""
    db = SessionLocal()
    try:
        pending = (
            db.query(Magazine)
            .filter(
                Magazine.scan_status == ScanStatus.done,
                Magazine.toc_status == OcrStatus.done,
                Magazine.themed_at.is_(None),
            )
            .order_by(Magazine.id)
            .limit(THEME_BATCH_SIZE)
            .all()
        )
        if not pending:
            return

        magazine_ids = [m.id for m in pending]
        magazines_with_articles = [
            (m, db.query(Article).filter(Article.magazine_id == m.id).order_by(Article.start_page).all())
            for m in pending
        ]

        try:
            results = assign_themes_batch(db, magazines_with_articles)
        except Exception:  # noqa: BLE001 - best-effort: left without themes, picked up again next run
            logger.exception("Batch theme assignment failed for magazines %s", magazine_ids)
            return

        for magazine, _articles in magazines_with_articles:
            theme_names = results.get(magazine.id)
            magazine = db.get(Magazine, magazine.id)
            magazine.themed_at = func.now()
            if not theme_names:
                db.commit()
                continue
            themes = []
            seen_ids = set()
            for name in theme_names:
                theme = db.query(Theme).filter(func.lower(Theme.name) == name.lower()).first()
                if theme is None:
                    theme = Theme(name=name)
                    db.add(theme)
                    db.flush()
                if theme.id not in seen_ids:
                    seen_ids.add(theme.id)
                    themes.append(theme)
            magazine.themes = themes
            db.commit()
    finally:
        db.close()


def _assign_magazine_themes(db, magazine: Magazine, force: bool = False) -> None:
    """Best-effort, one-time: generated once at indexing time from the
    magazine's sommaire, then left alone - not something to redo on every
    TOC retry. Failure here must not affect toc_status. `force=True` (used
    by the admin "Régénérer les thématiques" action) bypasses the
    already-has-themes guard, e.g. to retry a magazine that got 0 themes
    from a transient Gemini issue."""
    try:
        if magazine.themes and not force:
            return
        articles = db.query(Article).filter(Article.magazine_id == magazine.id).order_by(Article.start_page).all()
        theme_names = generate_magazine_themes(db, articles)
        if not theme_names:
            return

        themes = []
        seen_ids = set()
        for name in theme_names:
            theme = db.query(Theme).filter(func.lower(Theme.name) == name.lower()).first()
            if theme is None:
                theme = Theme(name=name)
                db.add(theme)
                db.flush()
            if theme.id not in seen_ids:
                seen_ids.add(theme.id)
                themes.append(theme)

        magazine.themes = themes
        db.commit()
    except Exception:  # noqa: BLE001 - non-fatal, sommaire itself already succeeded
        db.rollback()
        logger.exception("Theme generation failed for magazine %s", magazine.id)


def recover_orphaned_processing_magazines() -> list[int]:
    """Called once when the worker process starts up. `handle_process_magazine_failure`
    only fires when RQ itself kills a job (e.g. job_timeout) while the worker
    process stays alive to run the callback - it can't run at all if the
    whole worker container was torn down mid-job by a deploy/restart, which
    leaves the magazine stuck at scan_status=processing forever (and the
    dashboard's scan-progress bar spinning forever, since it waits for every
    magazine to reach done/failed). Since this runs before the worker takes
    any job off the queue, any magazine still marked "processing" at this
    point cannot have a job genuinely in flight - it was orphaned by the
    previous worker process dying."""
    db = SessionLocal()
    try:
        orphaned = db.query(Magazine).filter(Magazine.scan_status == ScanStatus.processing).all()
        ids = [m.id for m in orphaned]
        for magazine in orphaned:
            magazine.scan_status = ScanStatus.failed
            magazine.error_message = "Traitement interrompu (redémarrage du worker) - relancez si nécessaire."
        db.commit()
        if ids:
            logger.warning("Recovered %d magazine(s) orphaned by a previous worker shutdown: %s", len(ids), ids)
        return ids
    finally:
        db.close()


def handle_process_magazine_failure(job, connection, type, value, traceback) -> None:  # noqa: A002 - RQ's fixed callback signature
    """RQ invokes this even when the job was killed for exceeding
    job_timeout (e.g. a hung OCR run on an oversized/corrupt PDF) - in that
    case process_magazine's own except block never runs, since the worker
    process was terminated, which would otherwise leave the magazine stuck
    at scan_status=processing forever with no way to notice or retry it."""
    magazine_id = job.args[0] if job.args else None
    if magazine_id is None:
        return
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is not None and magazine.scan_status == ScanStatus.processing:
            magazine.scan_status = ScanStatus.failed
            magazine.error_message = f"{type.__name__ if type else 'Erreur'}: {value}"[:2000]
            db.commit()
            logger.error("Magazine %s marked failed after job failure/timeout: %s", magazine_id, value)
    except Exception:  # noqa: BLE001 - this IS the failure handler, must never itself raise into RQ
        db.rollback()
        logger.exception("Failed to mark magazine %s failed after job failure/timeout", magazine_id)
    finally:
        clear_magazine_progress(magazine_id)
        db.close()


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

        total_pages = get_page_count(processed_path)
        cover_text = None
        for page_data in extract_pages(processed_path):
            if page_data["page_number"] == 1:
                cover_text = page_data["raw_text"]
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
            set_magazine_progress(magazine_id, page_data["page_number"], total_pages)

        if cover_text and (magazine.publication_date is None or magazine.issue_number is None):
            if magazine.publication_date is None:
                cover_year = extract_year_from_cover_text(cover_text)
                if cover_year:
                    magazine.publication_date = datetime(cover_year, 1, 1, tzinfo=timezone.utc)
            if magazine.issue_number is None:
                magazine.issue_number = extract_issue_number_from_cover_text(cover_text)

        magazine.scan_status = ScanStatus.done
        magazine.error_message = None
        db.commit()
        logger.info("Magazine %s processed successfully", magazine_id)

        extract_and_store_articles(db, magazine)
        ingestion_queue.enqueue(process_pending_theme_batch, job_timeout="15m")
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
        clear_magazine_progress(magazine_id)
        db.close()


def retry_toc(magazine_id: int) -> None:
    """Re-runs the local sommaire extraction for a single magazine - e.g.
    after fixing/reprocessing its OCR text."""
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is None:
            logger.warning("Magazine %s not found, skipping TOC retry", magazine_id)
            return
        extract_and_store_articles(db, magazine)
    finally:
        db.close()


def regenerate_magazine_themes(magazine_id: int) -> None:
    """Force-regenerate a magazine's themes even if it already has some -
    triggered from the admin "Régénérer les thématiques" action, e.g. to
    retry magazines left at 0 themes by a past transient Gemini failure."""
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is None:
            logger.warning("Magazine %s not found, skipping theme regeneration", magazine_id)
            return
        _assign_magazine_themes(db, magazine, force=True)
    finally:
        db.close()


def reindex_magazine(magazine_id: int) -> None:
    """Re-push every page of a magazine to Meilisearch, e.g. after its
    category changed, so full-text search filtering picks it up."""
    db = SessionLocal()
    try:
        magazine = db.get(Magazine, magazine_id)
        if magazine is None:
            logger.warning("Magazine %s not found, skipping reindex", magazine_id)
            return
        pages = db.query(Page).filter(Page.magazine_id == magazine_id).all()
        index_pages(pages, magazine)
    finally:
        db.close()
