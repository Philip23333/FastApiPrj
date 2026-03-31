from sqlalchemy import select, func, delete
from models.favorite import Favorite
from models.news import News

#  检查用户是否已收藏某条新闻
async def is_favorited(db, user_id: int, news_id: int) -> bool:
    stmt = select(Favorite.id).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none() is not None

async def news_exists(db, news_id: int) -> bool:
    stmt = select(News.id).where(News.id == news_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none() is not None


# 获取用户收藏的总数
async def get_favorites_count_by_user(db, user_id: int) -> int:
    stmt = select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
    res = await db.execute(stmt)
    return res.scalar_one() or 0

# 获取用户收藏的新闻列表
async def get_favorites_by_user(db, user_id: int, offset: int = 0, limit: int = 10):
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

# 创建收藏记录
async def create_favorite(db, user_id: int, news_id: int) -> Favorite:
    favorite = Favorite(user_id=user_id, news_id=news_id)
    db.add(favorite)
    await db.flush()
    await db.refresh(favorite)
    return favorite

# 删除收藏记录
async def delete_favorite(db, user_id: int, news_id:int) -> bool:
    stmt = delete(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    res = await db.execute(stmt)
    await db.flush()
    return res.rowcount > 0

