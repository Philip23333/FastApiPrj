from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from crud import news as news_crud
from dependencies.auth import get_current_reviewer_or_admin_user, get_current_user
from models.user import User
from schemas.ai import (
    AIRAGChunkListOut,
    AIRAGClearOut,
    AIChatIn,
    AIChatOut,
    AINewsChatIn,
    AIQAIn,
    AIQAOut,
    AIRAGIndexStatusOut,
    AINewsDraftSuggestIn,
    AINewsDraftSuggestOut,
    AINewsSummaryOut,
)
from services.ai.client import AIClient, AIClientError
from services.ai.rag_service import rag_service
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


@router.post("/news/{news_id}/chat", response_model=ApiResponse[AIChatOut])
async def chat_with_news(
    news_id: int,
    payload: AINewsChatIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    item = await news_crud.get_news_by_id_plain(db, news_id)
    if not item or item.is_deleted:
        raise HTTPException(status_code=404, detail="新闻不存在")

    service = AIService()
    try:
        answer, model = await service.chat_about_news(
            title=item.title,
            description=item.description,
            content=item.content,
            question=payload.question,
            temperature=payload.temperature,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(AIChatOut(answer=answer, model=model), message="新闻对话成功")


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


@router.post("/qa", response_model=ApiResponse[AIQAOut])
async def qa_with_rag(
    payload: AIQAIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    # 首次使用自动构建索引，避免前端初次调用体验中断。
    if rag_service.get_status().indexed_chunk_count == 0:
        await rag_service.rebuild_index(db)

    client = AIClient()
    try:
        result = await rag_service.answer_question(
            question=payload.question,
            top_k=payload.top_k,
            ai_client=client,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(result, message="RAG问答成功")


@router.post("/rag/index/rebuild", response_model=ApiResponse[AIRAGIndexStatusOut])
async def rag_rebuild_index(
    db: AsyncSession = Depends(get_db),
    current_admin_or_reviewer: User = Depends(get_current_reviewer_or_admin_user),
):
    _ = current_admin_or_reviewer

    try:
        status = await rag_service.rebuild_index(db)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return success_response(status, message="RAG索引重建完成")


@router.get("/rag/index/status", response_model=ApiResponse[AIRAGIndexStatusOut])
async def rag_index_status(
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return success_response(rag_service.get_status(), message="RAG索引状态")


@router.get("/rag/chunks", response_model=ApiResponse[AIRAGChunkListOut])
async def rag_list_chunks(
    page: int = 1,
    size: int = 20,
    news_id: int | None = None,
    current_admin_or_reviewer: User = Depends(get_current_reviewer_or_admin_user),
):
    _ = current_admin_or_reviewer
    try:
        data = rag_service.list_chunks(page=page, size=size, news_id=news_id)
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(data, message="RAG切片列表")


@router.delete("/rag/index", response_model=ApiResponse[AIRAGClearOut])
async def rag_clear_index(
    current_admin_or_reviewer: User = Depends(get_current_reviewer_or_admin_user),
):
    _ = current_admin_or_reviewer
    try:
        rag_service.clear_index()
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        AIRAGClearOut(cleared=True, collection_name=rag_service.collection_name),
        message="RAG索引已清空",
    )
