import json

from app.queue import redis_conn

PROGRESS_KEY_TTL_SECONDS = 3600
_PROGRESS_KEY_PREFIX = "magazine_progress"


def set_magazine_progress(magazine_id: int, current: int, total: int) -> None:
    """Live page-processing progress for a magazine currently being OCR'd
    and indexed - stored in Redis (not the DB) since it's purely transient,
    polled by the admin dashboard to show a percentage instead of a bare
    "en cours" badge with no sense of how far along it is."""
    redis_conn.setex(
        f"{_PROGRESS_KEY_PREFIX}:{magazine_id}",
        PROGRESS_KEY_TTL_SECONDS,
        json.dumps({"current": current, "total": total}),
    )


def get_magazine_progress(magazine_id: int) -> dict | None:
    raw = redis_conn.get(f"{_PROGRESS_KEY_PREFIX}:{magazine_id}")
    if raw is None:
        return None
    return json.loads(raw)


def clear_magazine_progress(magazine_id: int) -> None:
    redis_conn.delete(f"{_PROGRESS_KEY_PREFIX}:{magazine_id}")
