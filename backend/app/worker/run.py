import logging

import redis
from rq import Queue, Worker

from app.config import get_settings
from app.database import engine
from app.logging_config import configure_logging
from app.worker.tasks import recover_orphaned_processing_magazines

configure_logging("worker")
logger = logging.getLogger("worker")


def main() -> None:
    settings = get_settings()
    conn = redis.Redis(host=settings.redis_host, port=settings.redis_port)
    recover_orphaned_processing_magazines()
    # RQ forks a fresh OS process per job. Without this, the connection
    # recover_orphaned_processing_magazines() just used stays checked into
    # the pool here in the long-lived parent process, and the first forked
    # job would inherit it - two processes then sharing one PostgreSQL
    # session, which can surface as e.g. "prepared statement ... already
    # exists". close=False avoids actually closing the (still valid, still
    # in use) connection out from under this process - it just drops the
    # pool's references so a future checkout opens a brand new one instead.
    engine.dispose(close=False)
    worker = Worker([Queue("ingestion", connection=conn)], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
