import json
from pathlib import Path
from typing import Iterator

from app.logging_config import BACKUP_COUNT, LOG_DIR

COMPONENTS = ["backend", "worker"]


def _read_log_file(path: Path, component: str) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry["component"] = component
            yield entry


def read_logs(level: str | None = None, component: str | None = None, limit: int = 200) -> list[dict]:
    components = [component] if component else COMPONENTS
    entries: list[dict] = []
    for comp in components:
        if comp not in COMPONENTS:
            continue
        # RotatingFileHandler keeps the current file plus up to
        # BACKUP_COUNT rotated ones (component.log.1, .2, ...) - reading
        # only the current file meant the admin view would go completely
        # blank right after a rotation, with everything sitting unread in
        # the backup(s) until enough new activity accumulated again.
        entries.extend(_read_log_file(LOG_DIR / f"{comp}.log", comp))
        for i in range(1, BACKUP_COUNT + 1):
            entries.extend(_read_log_file(LOG_DIR / f"{comp}.log.{i}", comp))

    if level:
        level = level.upper()
        entries = [e for e in entries if e.get("level") == level]

    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:limit]
