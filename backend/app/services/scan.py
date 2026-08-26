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
from app.models import Magazine, ScanStatus
from app.queue import ingestion_queue, redis_conn
from app.worker.tasks import process_magazine

logger = logging.getLogger("app.scan")
settings = get_settings()

STABILITY_DELAY_SECONDS = 8
SCAN_JOB_TTL_SECONDS = 24 * 3600
SCAN_JOB_REDIS_PREFIX = "scan_job"


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_snapshot(path: Path) -> tuple[int, float]:
    st = path.stat()
    return st.st_size, st.st_mtime


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

    new_magazine_ids: list[int] = []
    for path in stable_paths:
        file_hash = _sha256_of_file(path)
        if file_hash in known_hashes:
            continue

        size, mtime = candidates[path]
        magazine = Magazine(
            title=path.stem,
            filename=path.name,
            file_path=str(path.relative_to(nas_root)),
            file_hash=file_hash,
            file_size=size,
            file_mtime=datetime.fromtimestamp(mtime, tz=timezone.utc),
            scan_status=ScanStatus.stable,
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

    return job_id, len(new_magazine_ids)


def get_scan_job_magazine_ids(job_id: str) -> list[int] | None:
    raw = redis_conn.get(f"{SCAN_JOB_REDIS_PREFIX}:{job_id}")
    if raw is None:
        return None
    return json.loads(raw)
