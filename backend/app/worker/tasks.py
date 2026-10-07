import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models import Article, Magazine, OcrStatus, Page, PageLanguage, ScanStatus
from app.services.issue_parser import extract_issue_number_from_cover_text, extract_year_from_cover_text
from app.services.meili import ensure_index_configured, index_page, index_pages
from app.services.progress import clear_magazine_progress, set_magazine_progress
from app.services.sommaire_ocr import analyser_absence_de_sommaire, extract_articles_from_ocr
from app.services.import_sous_thematiques import rattacher_magazine
from app.worker.ocr import detect_language, ensure_text_layer, extract_pages, get_page_count, render_cover_thumbnail

logger = logging.getLogger("worker.tasks")


def message_erreur_affichable(exc: BaseException, longueur_max: int = 300) -> str:
    """Message court, sans trace ni chemin absolu, destiné au stockage en base.

    `error_message` est exposé par l'API à tout utilisateur authentifié : y
    écrire la trace Python complète y publiait l'arborescence du serveur et la
    structure interne du code. La trace intégrale reste disponible dans les
    logs applicatifs, réservés à l'administration.
    """
    texte = f"{type(exc).__name__}: {exc}"
    # Ne conserve que le nom de fichier des chemins absolus rencontrés.
    texte = re.sub(r"/(?:[^/\s]+/)+", "", texte)
    return texte[:longueur_max]
settings = get_settings()


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
        if entries:
            magazine.toc_error_message = None
        else:
            # Aucune entrée : reste à savoir si c'est un numéro sans sommaire
            # ou un sommaire qu'on n'a pas su lire. Les deux appellent des
            # actions opposées, et les confondre rend le second invisible.
            message, pages_sommaire = analyser_absence_de_sommaire(pages)
            magazine.toc_error_message = message
            if pages_sommaire:
                # Une page de sommaire a bien été repérée et n'a rien donné :
                # c'est un échec de lecture, pas une absence. Le laisser en
                # « done » était un faux succès — plus insidieux qu'une erreur
                # franche, puisque rien ne le signalait dans l'interface.
                magazine.toc_status = OcrStatus.failed
            # Sans page repérée, on garde « done » : un numéro peut
            # légitimement ne pas comporter de sommaire, et le marquer en
            # échec ferait remonter du bruit qu'aucune action ne résoudrait.
        db.commit()

        # Les articles tout juste extraits rejoignent les sous-thématiques
        # existantes, par simple correspondance des mots-clés déjà en base.
        # Aucun appel à un modèle, quelques millisecondes — c'est ce qui rend
        # la navigation par sujet vivante sans intervention manuelle.
        #
        # Enveloppé : un échec ici ne doit pas faire passer le sommaire en
        # erreur alors qu'il a été extrait correctement.
        try:
            bilan = rattacher_magazine(db, magazine.id)
            if bilan["rattachements"]:
                logger.info(
                    "Magazine %s : %s article(s) rattaché(s) à une sous-thématique",
                    magazine.id,
                    bilan["rattachements"],
                )
        except Exception:  # noqa: BLE001 - le sommaire, lui, est bien enregistré
            db.rollback()
            logger.exception("Rattachement aux sous-thématiques échoué pour %s", magazine.id)
    except Exception as exc:  # noqa: BLE001 - non-fatal, reported on the magazine row
        db.rollback()
        magazine = db.get(Magazine, magazine.id)
        if magazine is not None:
            magazine.toc_status = OcrStatus.failed
            magazine.toc_error_message = message_erreur_affichable(exc)
            db.commit()
        logger.exception("Sommaire extraction failed for magazine %s", magazine.id)


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
            # Même assainissement que message_erreur_affichable : ici RQ nous
            # passe le type et la valeur séparément, pas l'exception elle-même.
            magazine.error_message = re.sub(
                r"/(?:[^/\s]+/)+", "", f"{type.__name__ if type else 'Erreur'}: {value}"
            )[:300]
            db.commit()
            logger.error("Magazine %s marked failed after job failure/timeout: %s", magazine_id, value)
    except Exception:  # noqa: BLE001 - this IS the failure handler, must never itself raise into RQ
        db.rollback()
        logger.exception("Failed to mark magazine %s failed after job failure/timeout", magazine_id)
    finally:
        # Le nettoyage Redis ne doit ni masquer l'exception d'origine ni
        # empêcher la fermeture de la session : un Redis injoignable ici
        # laissait fuir une connexion PostgreSQL à chaque job.
        try:
            clear_magazine_progress(magazine_id)
        except Exception:  # noqa: BLE001 - nettoyage best-effort
            logger.warning("Nettoyage de la progression impossible pour %s", magazine_id, exc_info=True)
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
        # .webp depuis la bascule d'encodage. Les vignettes deja produites en
        # .png restent servies telles quelles : l'endpoint choisit son type MIME
        # d'apres l'extension reelle, et le chemin est stocke en base.
        cover_path = cover_dir / f"{magazine.id}.webp"
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
        # Le thémage Gemini par numéro n'est plus déclenché à l'ingestion : la
        # navigation par sujet passe désormais par la taxonomie par article,
        # construite hors ligne puis importée. Laisser cet enfilement dépensait
        # le quota Gemini (20 requêtes par jour) pour alimenter une table que
        # plus aucun écran ne lit. Le lot reste déclenchable à la demande
        # depuis l'administration.
    except Exception as exc:  # noqa: BLE001 - failure is reported on the magazine row, not re-raised silently
        db.rollback()
        magazine = db.get(Magazine, magazine_id)
        if magazine is not None:
            magazine.scan_status = ScanStatus.failed
            magazine.error_message = message_erreur_affichable(exc)
            db.commit()
        # La trace complète va dans les logs, pas dans la réponse API.
        logger.exception("Failed to process magazine %s", magazine_id)
        raise
    finally:
        # Le nettoyage Redis ne doit ni masquer l'exception d'origine ni
        # empêcher la fermeture de la session : un Redis injoignable ici
        # laissait fuir une connexion PostgreSQL à chaque job.
        try:
            clear_magazine_progress(magazine_id)
        except Exception:  # noqa: BLE001 - nettoyage best-effort
            logger.warning("Nettoyage de la progression impossible pour %s", magazine_id, exc_info=True)
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
