from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# prepare_threshold=None disables psycopg3's server-side auto-prepare.
# Prepared statements are tied to their PostgreSQL session/connection - if
# a connection ever gets shared across a fork (RQ forks a fresh OS process
# per job) both processes can end up issuing "PREPARE" for the same
# statement name on what is, at the wire level, the same underlying
# session, which Postgres rejects with "prepared statement ... already
# exists". Disabling auto-prepare removes that whole failure class; see
# also worker/run.py, which disposes the engine before the fork loop
# starts so no connection is ever inherited by a forked worker in the
# first place.
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"prepare_threshold": None})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
