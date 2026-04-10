from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.like import Like
from models.news import News


async def is_liked(db: AsyncSession, user_id: int, news_id: int) -> bool:
    stmt = select(Like.id).where(Like.user_id == user_id, Like.news_id == news_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none() is not None


async def get_like_count_by_news(db: AsyncSession, news_id: int) -> int:
    stmt = select(func.count(Like.id)).where(Like.news_id == news_id)
    res = await db.execute(stmt)
    return int(res.scalar_one() or 0)


async def get_likes_count_by_user(db: AsyncSession, user_id: int) -> int:
    stmt = select(func.count(Like.id)).where(Like.user_id == user_id)
    res = await db.execute(stmt)
    return int(res.scalar_one() or 0)


async def get_likes_by_user(db: AsyncSession, user_id: int, offset: int = 0, limit: int = 10):
    stmt = (
        select(Like)
        .where(Like.user_id == user_id)
        .order_by(Like.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


async def create_like(db: AsyncSession, user_id: int, news_id: int) -> Like:
    like = Like(user_id=user_id, news_id=news_id)
    db.add(like)
    await db.flush()

    await db.execute(
        update(News)
        .where(News.id == news_id)
        .values(like_count=func.greatest(News.like_count + 1, 0))
    )

    await db.refresh(like)
    return like


async def delete_like(db: AsyncSession, user_id: int, news_id: int) -> bool:
    stmt = delete(Like).where(Like.user_id == user_id, Like.news_id == news_id)
    res = await db.execute(stmt)
    await db.flush()

    if res.rowcount:
        await db.execute(
            update(News)
            .where(News.id == news_id)
            .values(like_count=func.greatest(News.like_count - 1, 0))
        )
        await db.flush()
        return True

    return False
