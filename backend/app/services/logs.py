import json
from pathlib import Path
from typing import Iterator

from app.logging_config import LOG_DIR

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
        entries.extend(_read_log_file(LOG_DIR / f"{comp}.log", comp))

    if level:
        level = level.upper()
        entries = [e for e in entries if e.get("level") == level]

    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:limit]
