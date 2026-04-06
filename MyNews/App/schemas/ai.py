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
