"""Database setup."""
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

DATABASE_URL = (
    f"mysql+pymysql://{settings.db_user}:{quote(settings.db_password)}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
)

engine = create_engine(DATABASE_URL, echo=False, future=True)


def init_db() -> None:
    """Initialize database - import models only."""
    # 导入所有模型以确保 SQLModel.metadata 能够发现它们
    from app.models import (  # noqa: F401
        AdminSession,
        User,
        Task,
        TaskLog,
        UserActivityLog,
        UserImage,
        PostedMakeup,
    )
    # 注意：表已存在于数据库中，不执行 create_all 避免类型冲突
    # 如果需要创建新表，请手动执行或临时取消注释下一行
    # SQLModel.metadata.create_all(engine, checkfirst=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope."""
    with Session(engine) as session:
        yield session

