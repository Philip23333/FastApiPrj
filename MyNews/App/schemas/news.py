from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewsListItemOut(BaseModel):
    id: int
    title: str
    description: str
    category_name: str
    author: Optional[str] = None
    views: int
    like_count: int = 0
    comment_count: int = 0
    publish_time: datetime
    image: Optional[str] = None
    # 列表返回审核状态，便于后台筛选
    audit_status: str = "pending"


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
    like_count: int = 0
    comment_count: int = 0
    publish_time: datetime
    image: Optional[str] = None
    relevance: int
    audit_status: str = "pending"


class NewsDetailOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    content: str
    category_id: int
    category_name: str
    author: Optional[str] = None
    views: int
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    publish_time: datetime
    image: Optional[str] = None
    # 详情返回完整审核信息，供后台详情页展示
    audit_status: str = "pending"
    audit_remark: Optional[str] = None
    audited_by_user_id: Optional[int] = None
    audited_at: Optional[datetime] = None
    is_deleted: bool = False


class NewsAdminItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category_id: int
    category_name: str
    author: Optional[str] = None
    views: int
    like_count: int = 0
    comment_count: int = 0
    publish_time: datetime
    image: Optional[str] = None
    audit_status: str = "pending"
    audit_remark: Optional[str] = None
    audited_by_user_id: Optional[int] = None
    audited_at: Optional[datetime] = None


class NewsAuthorItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category_id: int
    category_name: str
    author: Optional[str] = None
    views: int
    like_count: int = 0
    comment_count: int = 0
    publish_time: datetime
    image: Optional[str] = None
    audit_status: str = "pending"
    audit_remark: Optional[str] = None
    audited_at: Optional[datetime] = None


class NewsAdminModerationIn(BaseModel):
    category_id: Optional[int] = None
    audit_status: Optional[Literal["pending", "approved", "rejected"]] = None
    audit_remark: Optional[str] = Field(None, max_length=500)


class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NewsCreate(BaseModel):
    title: str = Field(..., max_length=50)
    content: str
    category_id: int
    category_name: str
    author: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    # 后台创建/编辑时可显式设置审核状态；前台发布可不传，走模型默认 pending
    audit_status: Optional[str] = None
    audit_remark: Optional[str] = None
