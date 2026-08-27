import json
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("/data/logs")

# Each component (backend, worker) writes to its own file so two separate
# processes never fight over rotating the same file. ~12MB x 2 files
# (current + one backup) per component keeps the combined total under the
# requested 50MB cap.
MAX_BYTES_PER_FILE = 12 * 1024 * 1024
BACKUP_COUNT = 1


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def configure_logging(component: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / f"{component}.log",
        maxBytes=MAX_BYTES_PER_FILE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonLineFormatter())
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(stream_handler)
