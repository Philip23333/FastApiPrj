import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_chat import AIChatHistory, AIUserMemory


async def create_chat_history(
    db: AsyncSession,
    *,
    user_id: int,
    question: str,
    answer: str,
    citations: list[dict] | None,
    model: str | None,
) -> AIChatHistory:
    row = AIChatHistory(
        user_id=user_id,
        question=question,
        answer=answer,
        citations_json=json.dumps(citations or [], ensure_ascii=False),
        model=model,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_chat_history_count(db: AsyncSession, *, user_id: int) -> int:
    stmt = select(func.count(AIChatHistory.id)).where(AIChatHistory.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def get_chat_history_page(db: AsyncSession, *, user_id: int, offset: int, limit: int) -> list[AIChatHistory]:
    stmt = (
        select(AIChatHistory)
        .where(AIChatHistory.user_id == user_id)
        .order_by(AIChatHistory.created_at.desc(), AIChatHistory.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_recent_chat_history(db: AsyncSession, *, user_id: int, limit: int = 6) -> list[AIChatHistory]:
    stmt = (
        select(AIChatHistory)
        .where(AIChatHistory.user_id == user_id)
        .order_by(AIChatHistory.created_at.desc(), AIChatHistory.id.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def clear_chat_history(db: AsyncSession, *, user_id: int) -> int:
    stmt = delete(AIChatHistory).where(AIChatHistory.user_id == user_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


async def get_user_memory(db: AsyncSession, *, user_id: int) -> AIUserMemory | None:
    stmt = select(AIUserMemory).where(AIUserMemory.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_user_memory(db: AsyncSession, *, user_id: int, memory_text: str) -> AIUserMemory:
    row = await get_user_memory(db, user_id=user_id)
    if row is None:
        row = AIUserMemory(user_id=user_id, memory_text=memory_text)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    row.memory_text = memory_text
    await db.flush()
    await db.refresh(row)
    return row