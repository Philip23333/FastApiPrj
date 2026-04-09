from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreateIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentNewsItemOut(BaseModel):
    id: int
    news_id: int
    user_id: int
    username: str
    nickname: str | None = None
    content: str
    created_at: datetime


class CommentMineItemOut(BaseModel):
    id: int
    news_id: int
    title: str
    content: str
    created_at: datetime
