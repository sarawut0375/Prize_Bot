from sqlmodel import Session, SQLModel, create_engine

from pricebot.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    from pricebot import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
