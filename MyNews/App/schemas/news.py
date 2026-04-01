from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NewsListItemOut(BaseModel):
    id: int
    title: str
    description: str
    category_name: str
    author: Optional[str] = None
    views: int
    publish_time: datetime
    image: Optional[str] = None


class HotNewsItemOut(BaseModel):
    id: int
    title: str
    views: int


class SearchSuggestionOut(BaseModel):
    id: int
    title: str


class SearchNewsItemOut(BaseModel):
    id: int
    title: str
    description: str
    category_name: str
    author: Optional[str] = None
    views: int
    publish_time: datetime
    image: Optional[str] = None
    relevance: int


class NewsDetailOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    content: str
    category_id: int
    category_name: str
    author: Optional[str] = None
    views: int
    publish_time: datetime
    image: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class NewsCreate(BaseModel):
    title: str
    content: str
    category_id: int
    category_name: str
    author: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
