from datetime import datetime

from pydantic import BaseModel


class LikeListItemOut(BaseModel):
    id: int
    user_id: int
    news_id: int
    created_at: datetime


class NewsLikeSummaryOut(BaseModel):
    like_count: int
    is_liked: bool
