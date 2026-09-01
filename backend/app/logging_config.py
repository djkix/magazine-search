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
        message = record.getMessage()
        # logger.exception()/log(..., exc_info=True) previously had their
        # traceback silently dropped here, since only getMessage() was
        # used - leaving just a short message like "Batch sommaire
        # extraction failed for magazines [60, 78]" with no indication of
        # what actually failed, in the one place (this JSON log file) an
        # admin can see it without a shell into the container.
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
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

    # uvicorn configures "uvicorn.access"/"uvicorn.error" with their own
    # handlers and propagate=False, so they never reach the root logger
    # above - attach our file handler to them directly so HTTP request
    # activity actually shows up in the admin Logs view.
    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addHandler(file_handler)
