from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreateIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: int | None = Field(default=None, ge=1)


class CommentNewsItemOut(BaseModel):
    id: int
    news_id: int
    user_id: int
    username: str
    nickname: str | None = None
    content: str
    parent_comment_id: int | None = None
    created_at: datetime
    replies: list["CommentNewsItemOut"] = Field(default_factory=list)


class CommentMineItemOut(BaseModel):
    id: int
    news_id: int
    title: str
    content: str
    created_at: datetime


CommentNewsItemOut.model_rebuild()
