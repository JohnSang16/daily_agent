from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_session_factory(database_url: str):
    kw = {}
    if database_url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kw["poolclass"] = StaticPool
    return sessionmaker(create_engine(database_url, **kw))
