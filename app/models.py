"""Data models."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import Column, Enum, Field, SQLModel, JSON, Text
import enum

# 北京时间时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """获取当前北京时间（timezone-aware）。"""
    return datetime.now(BEIJING_TZ)


class TaskStatus(str, enum.Enum):
    """Task status."""

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class TaskType(str, enum.Enum):
    """Task type."""

    register = "register"
    login = "login"
    post = "post"
    makeup = "makeup"  # 保留用于向后兼容
    beauty_flow = "beauty_flow"
    # 模块任务类型
    create_user = "create_user"
    checkin = "checkin"
    face_upload = "face_upload"
    makeup_creation = "makeup_creation"
    post_community = "post_community"
    like_collect = "like_collect"
    like_comment = "like_comment"
    follow_user = "follow_user"
    collect_topic = "collect_topic"


class User(SQLModel, table=True):
    """User accounts."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str = Field(index=True)
    password_hash: str
    password_plain: Optional[str] = Field(default=None)
    token: Optional[str] = Field(default=None)
    makeup_preset_id: Optional[int] = Field(default=None, foreign_key="makeup_presets.id")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(default=None)


class MakeupPreset(SQLModel, table=True):
    """Makeup presets."""

    __tablename__ = "makeup_presets"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    meta: Optional[dict] = Field(sa_column=Column(JSON))
    source: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Post(SQLModel, table=True):
    """Post records."""

    __tablename__ = "posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    content: str
    media_ref: Optional[str] = Field(default=None)
    status: str = Field(default="pending")
    sent_at: Optional[datetime] = Field(default=None)
    api_resp: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Task(SQLModel, table=True):
    """Tasks to execute."""

    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    type: TaskType = Field(sa_column=Column(Enum(TaskType)))
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    scheduled_at: datetime
    status: TaskStatus = Field(default=TaskStatus.pending, sa_column=Column(Enum(TaskStatus)))
    attempts: int = Field(default=0)
    last_error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TaskLog(SQLModel, table=True):
    """Task execution logs."""

    __tablename__ = "task_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.pending, sa_column=Column(Enum(TaskStatus)))
    message: Optional[str] = Field(default=None)


class UserActivityLog(SQLModel, table=True):
    """User API call timeline."""

    __tablename__ = "user_activity_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    action: str
    api_endpoint: Optional[str] = Field(default=None)
    scheduled_at: Optional[datetime] = Field(default=None)
    executed_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="pending")
    message: Optional[str] = Field(default=None, sa_column=Column(Text))


class UserImage(SQLModel, table=True):
    """User avatar images stored in Cloudflare R2."""

    __tablename__ = "user_images"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    original_filename: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)
    content_type: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AdminSession(SQLModel, table=True):
    """Admin session tokens."""

    __tablename__ = "admin_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None)


class PostedMakeup(SQLModel, table=True):
    """妆造记录表，记录所有妆造及其发布状态."""

    __tablename__ = "makeups"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    makeup_id: int = Field(index=True, unique=True)  # 妆造ID唯一，避免重复
    created_at: datetime = Field(default_factory=beijing_now, index=True)  # 创建时间（北京时间）
    posted: bool = Field(default=False, index=True)  # 是否已发布
    posted_at: Optional[datetime] = Field(default=None, index=True)  # 发布时间