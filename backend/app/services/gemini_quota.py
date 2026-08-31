import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Setting
from app.queue import redis_conn

logger = logging.getLogger("app.gemini_quota")

DAILY_LIMIT_SETTING_KEY = "gemini_daily_request_limit"
# Matches the Gemini API free tier's observed generate_content cap per
# model per day - protects a fresh install out of the box even before an
# admin has looked at the setting. Once billing is enabled on the Gemini
# project this can be raised or disabled entirely (0/empty = unlimited).
DEFAULT_DAILY_LIMIT = 20
QUOTA_KEY_TTL_SECONDS = 26 * 3600

RPM_LIMIT_SETTING_KEY = "gemini_rpm_limit"
# Matches the free tier's observed requests-per-minute cap for
# gemini-3.5-flash. Unlike the daily cap, a per-minute limit is worth
# waiting out (seconds, not a day) instead of failing the whole job.
DEFAULT_RPM_LIMIT = 5
RPM_KEY_TTL_SECONDS = 90
# Bounded so a misconfigured/very low limit can't stall a worker job
# forever - after this many one-minute waits, give up and fail loudly
# instead of blocking the single worker indefinitely.
MAX_RPM_WAITS = 3


class GeminiQuotaExceeded(RuntimeError):
    """Raised instead of calling the Gemini API once today's self-imposed
    request budget for a model is used up."""


def get_gemini_daily_limit(db: Session) -> int | None:
    """None means unlimited."""
    row = db.get(Setting, DAILY_LIMIT_SETTING_KEY)
    if row is None:
        return DEFAULT_DAILY_LIMIT
    if not row.value:
        return None
    try:
        return int(row.value)
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def set_gemini_daily_limit(db: Session, limit: int | None) -> None:
    row = db.get(Setting, DAILY_LIMIT_SETTING_KEY)
    value = str(limit) if limit else ""
    if row:
        row.value = value
    else:
        db.add(Setting(key=DAILY_LIMIT_SETTING_KEY, value=value))
    db.commit()


def get_gemini_rpm_limit(db: Session) -> int | None:
    """None means unlimited."""
    row = db.get(Setting, RPM_LIMIT_SETTING_KEY)
    if row is None:
        return DEFAULT_RPM_LIMIT
    if not row.value:
        return None
    try:
        return int(row.value)
    except ValueError:
        return DEFAULT_RPM_LIMIT


def set_gemini_rpm_limit(db: Session, limit: int | None) -> None:
    row = db.get(Setting, RPM_LIMIT_SETTING_KEY)
    value = str(limit) if limit else ""
    if row:
        row.value = value
    else:
        db.add(Setting(key=RPM_LIMIT_SETTING_KEY, value=value))
    db.commit()


def _daily_key(model: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"gemini_quota:{model}:{day}"


def get_gemini_usage_today(model: str) -> int:
    """Read-only: how many of today's budget units have been spent for
    `model` so far, without consuming one - lets the admin UI show current
    usage instead of requiring a trip through the logs to check."""
    raw = redis_conn.get(_daily_key(model))
    return int(raw) if raw is not None else 0


def _wait_for_rpm_slot(model: str, limit: int) -> None:
    """Blocks briefly until under the per-minute cap instead of failing
    outright - a worker job has no interactive user waiting on it, so a
    short wait here is much safer for the account's standing than firing a
    request that would just get rejected with a 429 (or worse, contribute
    to the account being flagged for repeated abuse)."""
    for _ in range(MAX_RPM_WAITS):
        minute_bucket = int(time.time() // 60)
        key = f"gemini_rpm:{model}:{minute_bucket}"
        count = redis_conn.incr(key)
        if count == 1:
            redis_conn.expire(key, RPM_KEY_TTL_SECONDS)
        if count <= limit:
            return
        seconds_left = 60 - (time.time() % 60)
        logger.info("Gemini RPM limit reached for %s (%d/%d), waiting %.0fs", model, count, limit, seconds_left)
        time.sleep(seconds_left + 1)
    raise GeminiQuotaExceeded(f"Limite Gemini de requêtes/minute atteinte pour {model} - réessayez plus tard.")


def consume_gemini_quota(db: Session, model: str) -> None:
    """Call once immediately before every Gemini generate_content request.
    Enforces two independent caps to keep every job under the account's own
    rate limits (e.g. the free tier's 20 requests/day and 5 requests/minute
    for a given model) instead of firing requests Gemini would reject
    anyway - both to avoid noisy cascades of identical failures once a cap
    is hit, and to avoid the account being flagged/throttled harder for
    repeatedly hitting its limits:

    - Daily budget: hard cap: raises GeminiQuotaExceeded once spent, since
      waiting out a whole day inside a worker job isn't reasonable.
    - Per-minute budget: soft cap: waits a few seconds/minutes for a free
      slot, since it resets on its own within the same job's lifetime.
    """
    limit = get_gemini_daily_limit(db)
    if limit is not None and limit > 0:
        key = _daily_key(model)
        count = redis_conn.incr(key)
        if count == 1:
            redis_conn.expire(key, QUOTA_KEY_TTL_SECONDS)
        if count > limit:
            raise GeminiQuotaExceeded(
                f"Quota Gemini journalier atteint ({limit} requêtes/jour pour {model}) — réessayez demain."
            )
        logger.info("Gemini request %d/%d today for %s", count, limit, model)

    rpm_limit = get_gemini_rpm_limit(db)
    if rpm_limit is not None and rpm_limit > 0:
        _wait_for_rpm_slot(model, rpm_limit)


def mark_quota_exhausted_for_today(model: str) -> None:
    """Called when the API itself returns a 429 despite our own daily
    counter saying we were still under budget (e.g. the quota is shared
    with another tool using the same key, or the counter was reset by a
    Redis flush). Forces every further attempt today to short-circuit
    locally via consume_gemini_quota instead of hitting the network again -
    repeatedly tripping the account's rate limit is exactly the kind of
    abuse pattern that risks it being flagged."""
    redis_conn.set(_daily_key(model), 10**9, ex=QUOTA_KEY_TTL_SECONDS)
    logger.warning("Gemini returned 429 for %s - treating today's quota as exhausted", model)
