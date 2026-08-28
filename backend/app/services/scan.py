import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Collection, IssueType, Magazine, ScanStatus
from app.queue import ingestion_queue, redis_conn
from app.services.issue_parser import parse_issue_metadata
from app.worker.tasks import process_magazine, reindex_magazine

logger = logging.getLogger("app.scan")
settings = get_settings()

STABILITY_DELAY_SECONDS = 8
SCAN_JOB_TTL_SECONDS = 24 * 3600
SCAN_JOB_REDIS_PREFIX = "scan_job"
LATEST_SCAN_JOB_REDIS_KEY = "scan_job:latest"

_HS_RE = re.compile(r"\bhors[- ]s[ée]ries?\b|\bhs\b", re.IGNORECASE)
_SP_RE = re.compile(r"\bsp[ée]cia(?:l|ux)\b|\bsp\b", re.IGNORECASE)


def _detect_issue_type(title: str, dir_parts: tuple[str, ...] = ()) -> IssueType:
    """Checks the magazine title as well as any sub-directory it sits under
    within its collection (e.g. a "Hors Séries" or "Numéros Spéciaux"
    folder), since some collections are physically organized that way on
    the NAS instead of naming it in the file itself."""
    haystack = " ".join([title, *dir_parts])
    if _HS_RE.search(haystack):
        return IssueType.hs
    if _SP_RE.search(haystack):
        return IssueType.sp
    return IssueType.normal


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_snapshot(path: Path) -> tuple[int, float]:
    st = path.stat()
    return st.st_size, st.st_mtime


def _get_or_create_collection(db: Session, name: str, cache: dict[str, Collection]) -> Collection:
    """The top-level directory a PDF lives under (directly under the NAS
    root) names its collection - e.g. every issue under ".../Que Choisir/",
    including in any year or "Hors Séries" sub-folder beneath it, belongs to
    the "Que Choisir" collection. Created on first sight, reused after."""
    if name in cache:
        return cache[name]

    collection = db.query(Collection).filter(Collection.name == name).first()
    if collection is None:
        try:
            with db.begin_nested():
                collection = Collection(name=name)
                db.add(collection)
                db.flush()
        except IntegrityError:
            collection = db.query(Collection).filter(Collection.name == name).first()

    cache[name] = collection
    return collection


def _dir_parts(nas_root: Path, path: Path) -> tuple[str, ...]:
    """Directory components of `path` relative to `nas_root`, excluding the
    filename itself - e.g. ("Que Choisir", "Hors Séries")."""
    return path.relative_to(nas_root).parts[:-1]


def _collection_id_for(db: Session, dir_parts: tuple[str, ...], cache: dict[str, Collection]) -> int | None:
    if not dir_parts:
        return None
    return _get_or_create_collection(db, dir_parts[0], cache).id


def run_scan(db: Session) -> tuple[str, int]:
    """Walk the whole NAS mount (every directory, not just ones with new
    files) so that PDFs moved to a different directory since the last scan -
    e.g. reorganized into per-title folders - are found again by content
    hash and have their stored path and collection corrected, instead of
    being left pointing at a now-missing file.

    Returns (job_id, number_of_new_files_detected).
    """
    nas_root = Path(settings.nas_mount_path)
    if not nas_root.exists():
        raise FileNotFoundError(f"NAS mount path not found: {nas_root}")

    known_by_hash: dict[str, Magazine] = {m.file_hash: m for m in db.query(Magazine).all()}

    pdf_paths = sorted(nas_root.rglob("*.pdf"))
    candidates: dict[Path, tuple[int, float]] = {}
    for path in pdf_paths:
        try:
            snapshot = _stat_snapshot(path)
        except OSError:
            continue
        candidates[path] = snapshot

    if candidates:
        time.sleep(STABILITY_DELAY_SECONDS)

    stable_paths = []
    for path, first_snapshot in candidates.items():
        try:
            second_snapshot = _stat_snapshot(path)
        except OSError:
            continue
        if first_snapshot == second_snapshot:
            stable_paths.append(path)
        else:
            logger.info("Skipping unstable file (still being written): %s", path)

    collection_cache: dict[str, Collection] = {}
    new_magazine_ids: list[int] = []
    retry_ids: set[int] = set()
    relocated_ids: set[int] = set()

    for path in stable_paths:
        file_hash = _sha256_of_file(path)
        relative_path = str(path.relative_to(nas_root))

        existing = known_by_hash.get(file_hash)
        if existing is not None:
            if existing.file_path != relative_path:
                size, mtime = candidates[path]
                dir_parts = _dir_parts(nas_root, path)
                logger.info("Magazine %s relocated: %s -> %s", existing.id, existing.file_path, relative_path)
                existing.filename = path.name
                existing.file_path = relative_path
                existing.file_size = size
                existing.file_mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
                existing.collection_id = _collection_id_for(db, dir_parts, collection_cache)
                existing.issue_type = _detect_issue_type(existing.title, dir_parts[1:])
                if existing.scan_status == ScanStatus.failed:
                    existing.scan_status = ScanStatus.queued
                    existing.error_message = None
                    retry_ids.add(existing.id)
                db.commit()
                relocated_ids.add(existing.id)
            continue

        size, mtime = candidates[path]
        dir_parts = _dir_parts(nas_root, path)
        issue_number, publication_date, issue_month_label = parse_issue_metadata(path.stem)
        magazine = Magazine(
            title=path.stem,
            filename=path.name,
            file_path=relative_path,
            file_hash=file_hash,
            file_size=size,
            file_mtime=datetime.fromtimestamp(mtime, tz=timezone.utc),
            scan_status=ScanStatus.stable,
            collection_id=_collection_id_for(db, dir_parts, collection_cache),
            issue_type=_detect_issue_type(path.stem, dir_parts[1:]),
            issue_number=issue_number,
            publication_date=publication_date,
            issue_month_label=issue_month_label,
        )
        try:
            with db.begin_nested():
                db.add(magazine)
                db.flush()
        except IntegrityError:
            # Another concurrent scan inserted the same file_hash first.
            existing_race = db.query(Magazine).filter(Magazine.file_hash == file_hash).first()
            if existing_race is not None:
                known_by_hash[file_hash] = existing_race
            continue
        new_magazine_ids.append(magazine.id)
        known_by_hash[file_hash] = magazine

    db.commit()

    job_id = uuid.uuid4().hex
    for magazine_id in new_magazine_ids:
        magazine = db.get(Magazine, magazine_id)
        magazine.scan_status = ScanStatus.queued
        db.commit()
        ingestion_queue.enqueue(process_magazine, magazine_id, job_timeout="30m")

    for magazine_id in retry_ids:
        ingestion_queue.enqueue(process_magazine, magazine_id, job_timeout="30m")

    for magazine_id in relocated_ids:
        if magazine_id not in retry_ids:
            ingestion_queue.enqueue(reindex_magazine, magazine_id, job_timeout="10m")

    redis_conn.setex(
        f"{SCAN_JOB_REDIS_PREFIX}:{job_id}",
        SCAN_JOB_TTL_SECONDS,
        json.dumps(new_magazine_ids + list(retry_ids)),
    )
    redis_conn.setex(LATEST_SCAN_JOB_REDIS_KEY, SCAN_JOB_TTL_SECONDS, job_id)

    return job_id, len(new_magazine_ids)


def get_scan_job_magazine_ids(job_id: str) -> list[int] | None:
    raw = redis_conn.get(f"{SCAN_JOB_REDIS_PREFIX}:{job_id}")
    if raw is None:
        return None
    return json.loads(raw)


def get_latest_scan_job_id() -> str | None:
    """The most recently triggered scan's job id, so the dashboard can resume
    showing its progress after a page reload instead of only while the tab
    that triggered it stays open."""
    raw = redis_conn.get(LATEST_SCAN_JOB_REDIS_KEY)
    return raw.decode() if isinstance(raw, bytes) else raw


def backfill_collections(db: Session) -> list[int]:
    """Recompute every magazine's collection, issue_type, issue_number,
    publication_date and issue_month_label from its stored file path/title
    using the current rules. Covers both magazines scanned before this
    metadata was derived automatically, and ones mis-assigned by an older
    version of these heuristics (e.g. to a year or "Hors Séries"
    sub-directory instead of the collection's own top-level folder).
    Returns the ids of the magazines actually changed."""
    collection_cache: dict[str, Collection] = {}
    updated_ids: list[int] = []

    for magazine in db.query(Magazine).all():
        dir_parts = Path(magazine.file_path).parts[:-1]
        new_collection_id = _collection_id_for(db, dir_parts, collection_cache)
        new_issue_type = _detect_issue_type(magazine.title, dir_parts[1:])
        new_issue_number, new_publication_date, new_issue_month_label = parse_issue_metadata(magazine.title)

        changed = (
            magazine.collection_id != new_collection_id
            or magazine.issue_type != new_issue_type
            or magazine.issue_number != new_issue_number
            or magazine.publication_date != new_publication_date
            or magazine.issue_month_label != new_issue_month_label
        )
        if changed:
            magazine.collection_id = new_collection_id
            magazine.issue_type = new_issue_type
            magazine.issue_number = new_issue_number
            magazine.publication_date = new_publication_date
            magazine.issue_month_label = new_issue_month_label
            updated_ids.append(magazine.id)

    db.commit()
    return updated_ids
