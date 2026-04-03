from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HistoryListItemOut(BaseModel):
    id: int
    user_id: int
    news_id: int
    title: str
    description: Optional[str] = None
    category_name: Optional[str] = None
    views: int = 0
    image: Optional[str] = None
    is_removed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    view_time: Optional[datetime] = None
