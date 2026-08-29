import logging

import redis
from rq import Queue, Worker

from app.config import get_settings
from app.logging_config import configure_logging
from app.worker.tasks import recover_orphaned_processing_magazines

configure_logging("worker")
logger = logging.getLogger("worker")


def main() -> None:
    settings = get_settings()
    conn = redis.Redis(host=settings.redis_host, port=settings.redis_port)
    recover_orphaned_processing_magazines()
    worker = Worker([Queue("ingestion", connection=conn)], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
