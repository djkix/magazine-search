import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.logging_config import BACKUP_COUNT, LOG_DIR

# Antériorité à toute entrée réelle : sert de clé aux lignes dont
# l'horodatage est absent ou illisible, qui atterrissent ainsi en fin de
# liste au lieu de s'intercaler n'importe où.
_DATE_PLANCHER = datetime.min.replace(tzinfo=timezone.utc)


def _instant(entry: dict) -> datetime:
    """Clé de tri chronologique d'une entrée de journal.

    Les horodatages portent désormais leur décalage (« +02:00 »), mais les
    fichiers écrits avant ce changement n'en ont pas : ils étaient en UTC, on
    les y rattache explicitement. Sans cela, comparer une date naïve à une
    date située lèverait une TypeError, et un tri lexicographique
    intervertirait les deux formats à chaque changement d'heure.
    """
    try:
        horodatage = datetime.fromisoformat(entry.get("timestamp", ""))
    except (TypeError, ValueError):
        return _DATE_PLANCHER
    if horodatage.tzinfo is None:
        return horodatage.replace(tzinfo=timezone.utc)
    return horodatage

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

    entries.sort(key=_instant, reverse=True)
    return entries[:limit]
