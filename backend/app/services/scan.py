import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Collection, Magazine, ScanStatus
from app.queue import ingestion_queue, redis_conn
from app.worker.tasks import process_magazine

logger = logging.getLogger("app.scan")
settings = get_settings()

STABILITY_DELAY_SECONDS = 8
SCAN_JOB_TTL_SECONDS = 24 * 3600
SCAN_JOB_REDIS_PREFIX = "scan_job"
LATEST_SCAN_JOB_REDIS_KEY = "scan_job:latest"


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
    """The directory a PDF lives in (immediately under the NAS root or deeper)
    names its collection - e.g. every issue under ".../Que Choisir/" belongs
    to the "Que Choisir" collection. Created on first sight, reused after."""
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


def run_scan(db: Session) -> tuple[str, int]:
    """Walk the NAS mount, register genuinely new + stable PDFs, and enqueue them for OCR.

    Returns (job_id, number_of_new_files_detected).
    """
    nas_root = Path(settings.nas_mount_path)
    if not nas_root.exists():
        raise FileNotFoundError(f"NAS mount path not found: {nas_root}")

    known_hashes = {m.file_hash for m in db.query(Magazine.file_hash).all()}

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
    for path in stable_paths:
        file_hash = _sha256_of_file(path)
        if file_hash in known_hashes:
            continue

        size, mtime = candidates[path]
        collection_id = None
        if path.parent != nas_root:
            collection_id = _get_or_create_collection(db, path.parent.name, collection_cache).id

        magazine = Magazine(
            title=path.stem,
            filename=path.name,
            file_path=str(path.relative_to(nas_root)),
            file_hash=file_hash,
            file_size=size,
            file_mtime=datetime.fromtimestamp(mtime, tz=timezone.utc),
            scan_status=ScanStatus.stable,
            collection_id=collection_id,
        )
        try:
            with db.begin_nested():
                db.add(magazine)
                db.flush()
        except IntegrityError:
            # Another concurrent scan inserted the same file_hash first.
            known_hashes.add(file_hash)
            continue
        new_magazine_ids.append(magazine.id)
        known_hashes.add(file_hash)

    db.commit()

    job_id = uuid.uuid4().hex
    for magazine_id in new_magazine_ids:
        magazine = db.get(Magazine, magazine_id)
        magazine.scan_status = ScanStatus.queued
        db.commit()
        ingestion_queue.enqueue(process_magazine, magazine_id, job_timeout="30m")

    redis_conn.setex(
        f"{SCAN_JOB_REDIS_PREFIX}:{job_id}",
        SCAN_JOB_TTL_SECONDS,
        json.dumps(new_magazine_ids),
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
    """Assign a collection to every already-registered magazine that doesn't
    have one yet, inferred from its stored file path - for magazines that
    were scanned before collections were derived automatically. Returns the
    ids of the magazines updated."""
    collection_cache: dict[str, Collection] = {}
    updated_ids: list[int] = []

    magazines = db.query(Magazine).filter(Magazine.collection_id.is_(None)).all()
    for magazine in magazines:
        parent_name = Path(magazine.file_path).parent.name
        if not parent_name:
            continue
        magazine.collection_id = _get_or_create_collection(db, parent_name, collection_cache).id
        updated_ids.append(magazine.id)

    db.commit()
    return updated_ids
