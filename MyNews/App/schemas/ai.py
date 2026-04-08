from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class AIChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    system_prompt: Optional[str] = Field(None, max_length=2000)
    temperature: float = Field(0.3, ge=0, le=1)


class AINewsDraftSuggestIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    category_name: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1)
    description: Optional[str] = Field(None, max_length=300)


class AINewsSummaryOut(BaseModel):
    news_id: int
    summary: str
    key_points: List[str] = Field(default_factory=list)


class AINewsDraftSuggestOut(BaseModel):
    title_suggestions: List[str] = Field(default_factory=list)
    description_suggestion: Optional[str] = None
    content_suggestions: List[str] = Field(default_factory=list)


class AIChatOut(BaseModel):
    answer: str
    model: str


class AINewsChatIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    temperature: float = Field(0.2, ge=0, le=1)


class AIQAIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(4, ge=1, le=10)


class AIQACitationOut(BaseModel):
    news_id: int
    title: str
    snippet: str
    score: float


class AIQAOut(BaseModel):
    answer: str
    model: str
    citations: List[AIQACitationOut] = Field(default_factory=list)


class AIRAGIndexStatusOut(BaseModel):
    indexed_news_count: int
    indexed_chunk_count: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    last_rebuild_at: Optional[datetime] = None


class AIRAGChunkItemOut(BaseModel):
    point_id: str
    news_id: int
    title: str
    snippet: str
    category_name: str
    chunk_index: int
    publish_ts: float


class AIRAGChunkListOut(BaseModel):
    items: List[AIRAGChunkItemOut] = Field(default_factory=list)
    page: int
    size: int
    total: int


class AIRAGClearOut(BaseModel):
    cleared: bool
    collection_name: str
