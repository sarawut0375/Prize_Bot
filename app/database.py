"""
Database engine / session setup (SQLModel on top of SQLite by default).
"""
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    # Import models here so they are registered with SQLModel's metadata
    # before create_all() is called.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
