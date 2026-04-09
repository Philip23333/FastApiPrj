import json
import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from crud import ai_chat as ai_chat_crud
from crud import news as news_crud
from dependencies.auth import get_current_reviewer_or_admin_user, get_current_user
from models.user import User
from schemas.ai import (
    AIClearHistoryOut,
    AIChatHistoryItemOut,
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
    AIUserMemoryOut,
)
from services.ai.client import AIClient, AIClientError
from services.ai.memory_service import ai_memory_service
from services.ai.rag_service import rag_service
from services.ai.service import AIService
from utils.response import ApiResponse, PaginatedData, paginated_response, success_response

router = APIRouter(prefix="/ai", tags=["ai"])


def _sse_payload(event: str, data: dict) -> str:
    """将事件和数据编码成 SSE 文本块。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_memory_text(existing: str | None, question: str, answer: str) -> str:
    """拼接用户长期记忆，并限制最大长度避免提示词无限增长。"""
    prefix = (existing or "").strip()
    qa_line = f"Q: {question}\nA: {answer[:240]}"
    merged = f"{prefix}\n\n{qa_line}".strip() if prefix else qa_line
    max_chars = 4000
    if len(merged) > max_chars:
        merged = merged[-max_chars:]
    return merged


def _parse_citations(value: str | None) -> list[dict]:
    """安全解析 citations_json，异常时返回空列表。"""
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _build_history_context(history_items: list[dict[str, Any]], limit: int = 5) -> list[str]:
    """将历史问答转换为 RAG 追加上下文文本。"""
    contexts: list[str] = []
    for item in history_items[:limit]:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question and answer:
            contexts.append(f"Q: {question}\nA: {answer[:220]}")
    return contexts


async def _load_user_memory_and_history_context(db: AsyncSession, user_id: int) -> tuple[str, list[str]]:
    """优先从缓存加载用户记忆/历史，不命中时回源数据库并回填缓存。"""
    cached_memory = await ai_memory_service.get_cached_memory(user_id)
    cached_history = await ai_memory_service.get_cached_history(user_id)

    user_memory_text = cached_memory
    if user_memory_text is None:
        memory_row = await ai_chat_crud.get_user_memory(db, user_id=user_id)
        user_memory_text = memory_row.memory_text if memory_row else ""
        await ai_memory_service.set_cached_memory(user_id, user_memory_text)

    if cached_history is None:
        recent_rows = await ai_chat_crud.get_recent_chat_history(db, user_id=user_id, limit=5)
        history_payload = [
            {
                "id": row.id,
                "question": row.question,
                "answer": row.answer,
                "citations": _parse_citations(row.citations_json),
                "model": row.model,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent_rows
        ]
        await ai_memory_service.set_cached_history(user_id, history_payload)
    else:
        history_payload = cached_history

    history_context = _build_history_context(history_payload, limit=5)
    return user_memory_text or "", history_context


async def _refresh_user_cache(db: AsyncSession, user_id: int, memory_text: str):
    """刷新用户问答历史缓存和长期记忆缓存。"""
    recent_rows = await ai_chat_crud.get_recent_chat_history(db, user_id=user_id, limit=10)
    history_payload = [
        {
            "id": row.id,
            "question": row.question,
            "answer": row.answer,
            "citations": _parse_citations(row.citations_json),
            "model": row.model,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in recent_rows
    ]
    await ai_memory_service.set_cached_history(user_id, history_payload)
    await ai_memory_service.set_cached_memory(user_id, memory_text)


async def _persist_qa_result(
    db: AsyncSession,
    user_id: int,
    question: str,
    answer: str,
    citations: list[dict],
    model: str | None,
    user_memory_text: str,
):
    """持久化问答结果并更新缓存。"""
    await ai_chat_crud.create_chat_history(
        db,
        user_id=user_id,
        question=question,
        answer=answer,
        citations=citations,
        model=model,
    )
    updated_memory = _build_memory_text(user_memory_text, question, answer)
    await ai_chat_crud.upsert_user_memory(db, user_id=user_id, memory_text=updated_memory)
    await db.commit()
    await _refresh_user_cache(db, user_id=user_id, memory_text=updated_memory)


@router.post("/chat", response_model=ApiResponse[AIChatOut])
async def ai_chat(
    payload: AIChatIn,
    current_user: User = Depends(get_current_user),
):
    """通用 AI 对话接口。"""
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
    """对指定新闻生成摘要和要点。"""
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
    """在指定新闻语境下进行问答。"""
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
    """为新闻草稿提供标题、摘要与正文建议。"""
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
    """同步 RAG 问答接口：返回完整答案与来源。"""
    _ = current_user
    user_memory_text, history_context = await _load_user_memory_and_history_context(db, current_user.id)

    # 请求链路不做自动重建，避免长时间阻塞整个服务。
    if rag_service.get_status().indexed_chunk_count == 0:
        raise HTTPException(status_code=400, detail="RAG索引为空，请先由管理员执行 /ai/rag/index/rebuild")

    client = AIClient()
    try:
        result = await rag_service.answer_question(
            question=payload.question,
            top_k=payload.top_k,
            ai_client=client,
            user_memory=user_memory_text,
            history_context=history_context,
        )
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 持久化历史与记忆（按用户ID），并刷新缓存。
    await _persist_qa_result(
        db=db,
        user_id=current_user.id,
        question=payload.question,
        answer=result.answer,
        citations=[c.dict() for c in result.citations],
        model=result.model,
        user_memory_text=user_memory_text,
    )

    return success_response(result, message="RAG问答成功")


@router.post("/qa/stream")
async def qa_with_rag_stream(
    payload: AIQAIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式 RAG 问答接口：先返回来源，再增量输出答案。"""
    _ = current_user

    async def event_generator():
        """SSE 生成器：组织上下文、流式拉取模型输出、落库并刷新缓存。"""
        try:
            user_memory_text, history_context = await _load_user_memory_and_history_context(db, current_user.id)

            if rag_service.get_status().indexed_chunk_count == 0:
                yield _sse_payload("error", {"message": "RAG索引为空，请先由管理员执行 /ai/rag/index/rebuild"})
                return

            yield _sse_payload("status", {"message": "正在检索相关内容..."})
            client = AIClient()
            messages, citations = await rag_service.build_qa_messages_and_citations(
                question=payload.question,
                top_k=payload.top_k,
                user_memory=user_memory_text,
                history_context=history_context,
            )
            yield _sse_payload("citations", {"citations": [c.dict() for c in citations]})
            yield _sse_payload("status", {"message": "正在生成回答...(stream-v2)"})

            answer_parts: list[str] = []
            async for part in client.chat_messages_stream(messages=messages, temperature=0.2):
                answer_parts.append(part)
                yield _sse_payload("delta", {"content": part})
                await asyncio.sleep(0)

            answer = "".join(answer_parts).strip() or "暂时没有生成回答。"
            model = client.model

            await _persist_qa_result(
                db=db,
                user_id=current_user.id,
                question=payload.question,
                answer=answer,
                citations=[c.dict() for c in citations],
                model=model,
                user_memory_text=user_memory_text,
            )

            yield _sse_payload(
                "done",
                {
                    "model": model,
                    "citations": [c.dict() for c in citations],
                },
            )
        except AIClientError as exc:
            yield _sse_payload("error", {"message": str(exc)})
        except Exception:
            yield _sse_payload("error", {"message": "RAG问答失败，请稍后重试"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/qa/history", response_model=ApiResponse[PaginatedData[AIChatHistoryItemOut]])
async def qa_history(
    page: int = 1,
    size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页获取当前用户的问答历史。"""
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    offset = (safe_page - 1) * safe_size

    rows = await ai_chat_crud.get_chat_history_page(db, user_id=current_user.id, offset=offset, limit=safe_size)
    total = await ai_chat_crud.get_chat_history_count(db, user_id=current_user.id)

    items = []
    for row in rows:
        try:
            citations = json.loads(row.citations_json) if row.citations_json else []
        except Exception:
            citations = []
        items.append(
            AIChatHistoryItemOut(
                id=row.id,
                question=row.question,
                answer=row.answer,
                citations=citations,
                model=row.model,
                created_at=row.created_at,
            )
        )

    return paginated_response(items, total=total, page=safe_page, size=safe_size, message="AI问答历史")


@router.get("/qa/memory", response_model=ApiResponse[AIUserMemoryOut])
async def qa_memory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取当前用户的长期记忆文本。"""
    memory_text = await ai_memory_service.get_cached_memory(current_user.id)
    updated_at = None
    if memory_text is None:
        row = await ai_chat_crud.get_user_memory(db, user_id=current_user.id)
        memory_text = row.memory_text if row else ""
        updated_at = row.updated_at if row else None
        await ai_memory_service.set_cached_memory(current_user.id, memory_text)
    return success_response(
        AIUserMemoryOut(user_id=current_user.id, memory_text=memory_text or "", updated_at=updated_at),
        message="AI用户记忆",
    )


@router.delete("/qa/history", response_model=ApiResponse[AIClearHistoryOut])
async def qa_history_clear(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空当前用户问答历史与长期记忆。"""
    deleted_count = await ai_chat_crud.clear_chat_history(db, user_id=current_user.id)
    await ai_chat_crud.upsert_user_memory(db, user_id=current_user.id, memory_text="")
    await db.commit()
    await ai_memory_service.invalidate_user_cache(current_user.id)
    return success_response(AIClearHistoryOut(deleted_count=deleted_count), message="AI问答历史已清空")


@router.post("/rag/index/rebuild", response_model=ApiResponse[AIRAGIndexStatusOut])
async def rag_rebuild_index(
    db: AsyncSession = Depends(get_db),
    current_admin_or_reviewer: User = Depends(get_current_reviewer_or_admin_user),
):
    """管理员重建 RAG 全量索引。"""
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
    """查询 RAG 索引状态。"""
    _ = current_user
    return success_response(rag_service.get_status(), message="RAG索引状态")


@router.get("/rag/chunks", response_model=ApiResponse[AIRAGChunkListOut])
async def rag_list_chunks(
    page: int = 1,
    size: int = 20,
    news_id: int | None = None,
    current_admin_or_reviewer: User = Depends(get_current_reviewer_or_admin_user),
):
    """分页查看 RAG 切片，支持按 news_id 过滤。"""
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
    """管理员清空 RAG 索引。"""
    _ = current_admin_or_reviewer
    try:
        rag_service.clear_index()
    except AIClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response(
        AIRAGClearOut(cleared=True, collection_name=rag_service.collection_name),
        message="RAG索引已清空",
    )
