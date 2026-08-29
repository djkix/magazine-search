import logging
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


def consume_gemini_quota(db: Session, model: str) -> None:
    """Call once immediately before every Gemini generate_content request.
    Spends one unit of today's budget for `model` and raises
    GeminiQuotaExceeded instead of letting the call through once that
    budget is spent - this keeps every job under the account's own daily
    rate limit (e.g. the free tier's 20 requests/day/model) instead of
    firing requests that Gemini itself would reject with a 429 anyway,
    which previously produced dozens of noisy identical failures once the
    quota was already exhausted for the day."""
    limit = get_gemini_daily_limit(db)
    if limit is None or limit <= 0:
        return

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"gemini_quota:{model}:{day}"
    count = redis_conn.incr(key)
    if count == 1:
        redis_conn.expire(key, QUOTA_KEY_TTL_SECONDS)
    if count > limit:
        raise GeminiQuotaExceeded(
            f"Quota Gemini journalier atteint ({limit} requêtes/jour pour {model}) — réessayez demain."
        )
