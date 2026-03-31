from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.history import History

#  查询所有历史记录
async def get_history_by_user(db: AsyncSession, user_id: int, offset: int = 0, limit: int = 10):
    stmt = (
        select(History)
        .where(History.user_id == user_id)
        .order_by(History.view_time.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

# 检查历史记录是否存在
async def history_exists(db: AsyncSession, user_id: int, news_id: int) -> bool:
    stmt = select(History).where(History.user_id == user_id, History.news_id == news_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none() is not None

# 增加历史记录
async def upsert_history_record(db: AsyncSession, user_id: int, news_id: int) -> History:
    # upsert: 存在则刷新更新时间，不存在则新增。
    stmt = select(History).where(History.user_id == user_id, History.news_id == news_id)
    res = await db.execute(stmt)
    existed = res.scalar_one_or_none()

    if existed is not None:
        await db.execute(
            update(History)
            .where(History.id == existed.id)
            .values(view_time=func.now())
        )
        await db.flush()
        await db.refresh(existed)
        return existed

    history = History(user_id=user_id, news_id=news_id, view_time=func.now())
    db.add(history)
    await db.flush()
    await db.refresh(history)
    return history

# 删除历史记录
async def delete_history_record(db: AsyncSession, user_id: int, news_id:int) -> bool:
    stmt = delete(History).where(History.user_id == user_id, History.news_id == news_id)
    res = await db.execute(stmt)
    await db.flush()
    return res.rowcount > 0

# 获取用户历史记录的总数
async def get_history_count_by_user(db: AsyncSession, user_id: int) -> int:
    stmt = select(func.count(History.id)).where(History.user_id == user_id)
    res = await db.execute(stmt)
    return res.scalar_one() or 0
