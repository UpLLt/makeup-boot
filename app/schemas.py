"""Pydantic schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import TaskStatus, TaskType


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    status: str

    class Config:
        orm_mode = True


class TaskRead(BaseModel):
    id: int
    user_id: Optional[int]
    type: TaskType
    scheduled_at: datetime
    status: TaskStatus
    attempts: int
    last_error: Optional[str]

    class Config:
        orm_mode = True


