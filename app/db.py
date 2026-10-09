"""Database engine and session factory (SQLite for demo/dev, PostgreSQL in production)."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if url.startswith("sqlite:///"):
        db_file = url.removeprefix("sqlite:///")
        if db_file not in ("", ":memory:"):
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    if url.startswith("postgres://"):  # some hosts still hand out the old scheme
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return create_engine(url, pool_pre_ping=True)


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def create_all(self) -> None:
        from app import models  # noqa: F401  (register tables)

        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
