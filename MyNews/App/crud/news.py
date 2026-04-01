from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case, or_
from sqlalchemy.orm import joinedload
from models.news import Category,News

# 根据id获取新闻
async def get_news_by_id(db: AsyncSession, news_id: int):
    stmt = select(News).options(joinedload(News.category)).where(News.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    
    if news:
        # 直接在 ORM 对象上增加浏览量
        news.views += 1
        await db.flush()
        await db.refresh(news)
        
    return news


async def get_news_by_id_plain(db: AsyncSession, news_id: int):
    stmt = select(News).options(joinedload(News.category)).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# 获取新闻分类列表
async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(Category).offset(skip).limit(limit)
    # 步骤1：先 await 执行查询拿到 Result 对象
    result = await db.execute(stmt)
    # 步骤2：再从这个结果对象里通过 scalars() 提取出所有的 Category 实例
    return result.scalars().all()

# 获取总新闻条数
async def get_news_count(db: AsyncSession):
    stmt = select(func.count(News.id))
    result = await db.execute(stmt)
    return result.scalar()

# 获取新闻列表 (分页，倒序，关联分类表防止N+1查询)
async def get_news(db: AsyncSession, skip: int = 0, limit: int = 10):
    stmt = select(News).options(joinedload(News.category)).order_by(desc(News.publish_time)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

# 获取某个分类下的新闻总条数
async def get_news_count_by_category(db: AsyncSession, category_id: int):
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar()

# 获取某个分类下的新闻列表 (分页，倒序，关联分类表防止N+1查询)
async def get_news_by_category(db: AsyncSession, category_id: int, skip: int = 0, limit: int = 10):
    stmt = select(News).options(joinedload(News.category)).where(News.category_id == category_id).order_by(desc(News.publish_time)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_hot_news(db: AsyncSession, min_views: int = 0, limit: int = 8, offset: int = 0):
    """
    获取热榜新闻：
    - min_views: 浏览量阈值（必须大于多少浏览量才能上热榜）
    - offset: 用于换一换功能的偏移量
    - limit: 每次取多少条
    """
    stmt = (
        select(News)
        .options(joinedload(News.category))
        .where(News.views >= min_views)
        .order_by(desc(News.views))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


def _build_search_condition(keyword: str):
    pattern = f"%{keyword}%"
    return or_(
        News.title.like(pattern),
        News.description.like(pattern),
        News.content.like(pattern),
    )


def _build_search_relevance(keyword: str):
    exact = keyword
    prefix = f"{keyword}%"
    contains = f"%{keyword}%"
    return case(
        (News.title == exact, 100),
        (News.title.like(prefix), 80),
        (News.title.like(contains), 60),
        (News.description.like(prefix), 40),
        (News.description.like(contains), 30),
        (News.content.like(contains), 10),
        else_=0,
    )


async def get_search_count(db: AsyncSession, keyword: str):
    condition = _build_search_condition(keyword)
    stmt = select(func.count(News.id)).where(condition)
    result = await db.execute(stmt)
    return result.scalar()


async def search_news(db: AsyncSession, keyword: str, skip: int = 0, limit: int = 10):
    condition = _build_search_condition(keyword)
    relevance = _build_search_relevance(keyword).label("relevance")
    stmt = (
        select(News, relevance)
        .options(joinedload(News.category))
        .where(condition)
        .order_by(desc(relevance), desc(News.publish_time), desc(News.views))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.all()


async def search_news_suggestions(db: AsyncSession, keyword: str, limit: int = 5):
    if limit <= 0:
        return []

    condition = News.title.like(f"%{keyword}%")
    relevance = case(
        (News.title == keyword, 100),
        (News.title.like(f"{keyword}%"), 80),
        (News.title.like(f"%{keyword}%"), 60),
        else_=0,
    ).label("relevance")

    stmt = (
        select(News.id, News.title, relevance)
        .where(condition)
        .order_by(desc(relevance), desc(News.views), desc(News.publish_time))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.all()


async def create_news(db: AsyncSession, news_in, category_id: int):
    new_news = News(
        title=news_in.title,
        description=news_in.description,
        content=news_in.content,
        image=news_in.image,
        author=news_in.author,
        category_id=category_id,
    )
    db.add(new_news)
    await db.flush()
    await db.refresh(new_news)
    return new_news


async def update_news(db: AsyncSession, db_news: News, news_in, category_id: int):
    db_news.title = news_in.title
    db_news.description = news_in.description
    db_news.content = news_in.content
    db_news.image = news_in.image
    db_news.category_id = category_id
    await db.flush()
    await db.refresh(db_news)
    return db_news


async def delete_news(db: AsyncSession, db_news: News):
    await db.delete(db_news)
    await db.flush()


async def get_category_by_id(db: AsyncSession, category_id: int):
    stmt = select(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    return result.scalars().first()