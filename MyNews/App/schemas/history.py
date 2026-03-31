from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HistoryListItemOut(BaseModel):
    id: int
    user_id: int
    news_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    view_time: Optional[datetime] = None
