from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_trader.config import get_settings


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_settings().database_url
    engine_options: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **engine_options)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


SessionFactory = create_session_factory()


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session


@contextmanager
def session_scope(factory: sessionmaker[Session] = SessionFactory) -> Iterator[Session]:
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

