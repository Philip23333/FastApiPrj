from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from crud import news as news_crud
from dependencies.auth import get_current_user
from models.user import User
from schemas.ai import (
    AIChatIn,
    AIChatOut,
    AINewsDraftSuggestIn,
    AINewsDraftSuggestOut,
    AINewsSummaryOut,
)
from services.ai.client import AIClient, AIClientError
from services.ai.service import AIService
from utils.response import ApiResponse, success_response

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ApiResponse[AIChatOut])
async def ai_chat(
    payload: AIChatIn,
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    client = AIClient()
    try:
        answer, model = await client.chat(
            user_message=payload.message,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(AIChatOut(answer=answer, model=model), message="AI 对话成功")


@router.post("/news/{news_id}/summary", response_model=ApiResponse[AINewsSummaryOut])
async def summarize_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    item = await news_crud.get_news_by_id_plain(db, news_id)
    if not item or item.is_deleted:
        raise HTTPException(status_code=404, detail="新闻不存在")

    service = AIService()
    try:
        result, model = await service.summarize_news(
            news_id=news_id,
            title=item.title,
            description=item.description,
            content=item.content,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(result, message=f"新闻总结成功(model={model})")


@router.post("/news/draft/suggest", response_model=ApiResponse[AINewsDraftSuggestOut])
async def suggest_news_draft(
    payload: AINewsDraftSuggestIn,
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    service = AIService()
    try:
        result, model = await service.suggest_news_draft(payload)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(result, message=f"草稿建议生成成功(model={model})")
