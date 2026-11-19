from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_session_factory(database_url: str):
    kw = {}
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        kw["connect_args"] = {"check_same_thread": False, "timeout": 30}  # wait out another writer
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kw["poolclass"] = StaticPool
    engine = create_engine(database_url, **kw)
    if is_sqlite:
        # WAL lets a writer (e.g. a sync job's own audit-log writes) proceed
        # without locking out other connections also writing to the same file.
        @event.listens_for(engine, "connect")
        def _set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return sessionmaker(engine)
