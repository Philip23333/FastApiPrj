from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.comment import Comment
from models.news import News
async def get_comments_count_by_news(db: AsyncSession, news_id: int) -> int:
    stmt = select(func.count(Comment.id)).where(Comment.news_id == news_id)
    res = await db.execute(stmt)
    return int(res.scalar_one() or 0)


async def get_comments_by_news(db: AsyncSession, news_id: int, offset: int = 0, limit: int = 20):
    stmt = (
        select(Comment)
        .options(joinedload(Comment.user))
        .where(Comment.news_id == news_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


async def get_comments_count_by_user(db: AsyncSession, user_id: int) -> int:
    stmt = select(func.count(Comment.id)).where(Comment.user_id == user_id)
    res = await db.execute(stmt)
    return int(res.scalar_one() or 0)


async def get_comments_by_user(db: AsyncSession, user_id: int, offset: int = 0, limit: int = 20):
    stmt = (
        select(Comment)
        .options(joinedload(Comment.news))
        .where(Comment.user_id == user_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Comment | None:
    stmt = select(Comment).where(Comment.id == comment_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def create_comment(
    db: AsyncSession,
    user_id: int,
    news_id: int,
    content: str,
    parent_comment_id: int | None = None,
) -> Comment:
    comment = Comment(user_id=user_id, news_id=news_id, content=content, parent_comment_id=parent_comment_id)
    db.add(comment)
    await db.flush()

    await db.execute(
        update(News)
        .where(News.id == news_id)
        .values(comment_count=func.greatest(News.comment_count + 1, 0))
    )

    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, comment_id: int, user_id: int, is_admin: bool = False) -> bool:
    stmt = select(Comment).where(Comment.id == comment_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        return False

    if not is_admin and record.user_id != user_id:
        return False

    news_id = record.news_id
    await db.delete(record)
    await db.flush()

    await db.execute(
        update(News)
        .where(News.id == news_id)
        .values(comment_count=func.greatest(News.comment_count - 1, 0))
    )
    await db.flush()
    return True
