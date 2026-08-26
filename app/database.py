"""SQLAlchemy database engine and session helpers."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


def get_db():
    """Yield one database session per request."""
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()

