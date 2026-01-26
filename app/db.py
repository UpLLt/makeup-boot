"""Database setup."""
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

DATABASE_URL = (
    f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
)

engine = create_engine(DATABASE_URL, echo=False, future=True)


def init_db() -> None:
    """Create tables."""
    # 导入所有模型以确保 SQLModel.metadata 能够发现它们
    from app.models import (  # noqa: F401
        AdminSession,
        User,
        MakeupPreset,
        Post,
        Task,
        TaskLog,
        UserActivityLog,
        UserImage,
        PostedMakeup,
    )
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope."""
    with Session(engine) as session:
        yield session

