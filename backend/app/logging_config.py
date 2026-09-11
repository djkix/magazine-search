import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Fuseau des horodatages écrits dans les journaux.
#
# Sans ce réglage, logging.Formatter.formatTime appelle time.localtime, et le
# fuseau local d'un conteneur Docker est UTC : la vue Journaux de l'admin
# affichait donc des heures en décalage de une à deux heures avec l'horloge de
# l'exploitant, ce qui rend pénible tout rapprochement avec un incident.
LOG_TIMEZONE = os.getenv("LOG_TIMEZONE", "Europe/Paris")

try:
    FUSEAU_JOURNAUX = ZoneInfo(LOG_TIMEZONE)
except (ZoneInfoNotFoundError, ValueError):
    # Repli explicite plutôt qu'un plantage au démarrage. L'horodatage porte
    # son décalage (« +00:00 »), donc la bascule reste visible à la lecture.
    FUSEAU_JOURNAUX = timezone.utc


def _horodatage_local(secondes: float) -> datetime:
    return datetime.fromtimestamp(secondes, FUSEAU_JOURNAUX)


# Vaut aussi pour %(asctime)s : la sortie console (docker logs) et celle
# d'uvicorn suivent le même fuseau que le fichier JSON.
#
# staticmethod() est nécessaire : une fonction Python assignée telle quelle
# comme attribut de classe devient un descripteur, et self.converter(...)
# lui injecte alors `self` en premier argument (TypeError : un argument de
# trop). time.localtime, la valeur par défaut, y échappe car c'est une
# fonction native, pas une fonction Python - ce que staticmethod imite ici.
logging.Formatter.converter = staticmethod(lambda secondes: _horodatage_local(secondes).timetuple())

# Chemin surchargeable par l'environnement. La valeur par défaut reste celle
# du conteneur, mais un chemin en dur empêchait de lancer le backend hors
# Docker (aucun /data sur une machine de développement) et faisait échouer
# l'import de app.main en CI, où ce répertoire n'est pas créable.
LOG_DIR = Path(os.getenv("LOG_DIR", "/data/logs"))

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
                # ISO 8601 avec décalage explicite (« 2026-09-11T11:29:40+02:00 »).
                # Le décalage n'est pas décoratif : sans lui, une entrée écrite
                # avant le passage à l'heure d'hiver est indiscernable de celle
                # écrite une heure plus tard, et le frontend ne peut pas la
                # convertir de façon fiable.
                "timestamp": _horodatage_local(record.created).isoformat(timespec="seconds"),
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
