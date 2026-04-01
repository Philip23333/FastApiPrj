import json
import logging
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config.db_config import get_db
from crud import news as news_crud
from dependencies.auth import get_current_user
from models.user import User
from schemas.news import CategoryOut, HotNewsItemOut, NewsCreate, NewsDetailOut, NewsListItemOut, SearchNewsItemOut, SearchSuggestionOut
from utils.response import ApiResponse, PaginatedData, paginated_response, success_response
from config.cache_config import redis_client

logger = logging.getLogger(__name__)
# 热门新闻缓存配置
HOT_CACHE_TTL_SECONDS = 60
HOT_CACHE_EMPTY_TTL_SECONDS = 20
HOT_CACHE_KEY_PREFIX = "news:hot:v1"

# 新闻列表/分类缓存配置
NEWS_LIST_CACHE_TTL_SECONDS = 60
CATEGORY_LIST_CACHE_TTL_SECONDS = 300
CATEGORY_NEWS_CACHE_TTL_SECONDS = 60
LIST_CACHE_EMPTY_TTL_SECONDS = 20
NEWS_LIST_CACHE_KEY_PREFIX = "news:list:v1"
CATEGORY_LIST_CACHE_KEY_PREFIX = "news:categories_list:v1"
CATEGORY_NEWS_CACHE_KEY_PREFIX = "news:categories_news:v1"

# 构建热门新闻缓存的 Redis key，包含参数信息以支持不同条件的缓存
def build_hot_cache_key(min_views: int, page: int, size: int) -> str:
    return f"{HOT_CACHE_KEY_PREFIX}:min:{min_views}:page:{page}:size:{size}"


def build_news_list_cache_key(page: int, size: int) -> str:
    return f"{NEWS_LIST_CACHE_KEY_PREFIX}:page:{page}:size:{size}"


def build_category_list_cache_key(skip: int, limit: int) -> str:
    return f"{CATEGORY_LIST_CACHE_KEY_PREFIX}:skip:{skip}:limit:{limit}"


def build_category_news_cache_key(category_id: int, page: int, size: int) -> str:
    return f"{CATEGORY_NEWS_CACHE_KEY_PREFIX}:{category_id}:page:{page}:size:{size}"


async def read_json_cache(cache_key: str) -> tuple[bool, object | None]:
    # 统一缓存读取逻辑：Redis 异常则降级，坏 JSON 会被删除并回源重建。
    try:
        cached = await redis_client.get(cache_key)
        if not cached:
            return True, None

        try:
            return True, json.loads(cached)
        except json.JSONDecodeError:
            logger.warning("cache decode failed, deleting bad key=%s", cache_key)
            try:
                await redis_client.delete(cache_key)
            except Exception as delete_exc:
                logger.warning("cache delete failed, key=%s, error=%s", cache_key, delete_exc)
            return True, None
    except Exception as exc:
        logger.warning("cache read failed, key=%s, error=%s", cache_key, exc)
        return False, None


async def write_json_cache(cache_key: str, payload: object, ttl: int, redis_available: bool):
    # 统一缓存写入逻辑：仅在 Redis 可用时写入，失败不影响主流程。
    if not redis_available:
        return
    try:
        # default=str 确保 datetime 等不可序列化对象可写入缓存。
        await redis_client.setex(cache_key, ttl, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as exc:
        logger.warning("cache write failed, key=%s, error=%s", cache_key, exc)

router = APIRouter(
    prefix="/news",
    tags=["news"],
)

# 搜索建议接口和搜索结果接口的实现，增加了输入校验和分页参数的安全处理，确保即使前端传入异常值也能正常响应。
@router.get("/search/suggest", response_model=ApiResponse[list[SearchSuggestionOut]])
async def get_search_suggestions(q: str, limit: int = 5, db: AsyncSession = Depends(get_db)):
    keyword = q.strip()
    if not keyword:
        return success_response([], message="search suggestions")

    safe_limit = max(1, min(limit, 5))
    rows = await news_crud.search_news_suggestions(db, keyword=keyword, limit=safe_limit)
    suggestions = [
        SearchSuggestionOut(
            id=row.id,
            title=row.title,
        )
        for row in rows
    ]
    return success_response(suggestions, message="search suggestions")


@router.get("/search", response_model=ApiResponse[PaginatedData[SearchNewsItemOut]])
async def search_news(q: str, page: int = 1, size: int = 10, db: AsyncSession = Depends(get_db)):
    keyword = q.strip()
    if not keyword:
        return paginated_response([], total=0, page=page, size=size, message="search results")

    safe_page = max(page, 1)
    safe_size = max(1, min(size, 50))
    skip = (safe_page - 1) * safe_size
    total = await news_crud.get_search_count(db, keyword=keyword)
    rows = await news_crud.search_news(db, keyword=keyword, skip=skip, limit=safe_size)

    items = [
        SearchNewsItemOut(
            id=n.id,
            title=n.title,
            description=n.description if n.description else (n.content[:100] + "..." if n.content else ""),
            category_name=n.category.name if n.category else "未知",
            author=n.author,
            views=n.views,
            publish_time=n.publish_time,
            image=n.image,
            relevance=int(relevance),
        )
        for (n, relevance) in rows
    ]

    return paginated_response(items, total=total, page=safe_page, size=safe_size, message="search results")


@router.post("/", response_model=ApiResponse[NewsDetailOut])
async def create_news(
    news_in: NewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="用户未登录")

    category = await news_crud.get_category_by_id(db, news_in.category_id)
    if not category:
        raise HTTPException(status_code=404, detail=f"分类ID {news_in.category_id} 不存在")

    input_category_name = (news_in.category_name or "").strip()
    if category.name != input_category_name:
        raise HTTPException(status_code=400, detail="分类ID与分类名称不匹配")

    if not news_in.author:
        news_in.author = current_user.username

    try:
        created = await news_crud.create_news(db, news_in, category_id=news_in.category_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # 发布后失效受影响缓存，保证列表和分类页可见新数据
    try:
        list_keys = await redis_client.keys(f"{NEWS_LIST_CACHE_KEY_PREFIX}:*")
        if list_keys:
            await redis_client.delete(*list_keys)

        category_keys = await redis_client.keys(f"{CATEGORY_NEWS_CACHE_KEY_PREFIX}:{created.category_id}:*")
        if category_keys:
            await redis_client.delete(*category_keys)
    except Exception as exc:
        logger.warning("cache clear failed after create news id=%s, error=%s", created.id, exc)

    payload = NewsDetailOut(
        id=created.id,
        title=created.title,
        description=created.description,
        content=created.content,
        category_id=created.category_id,
        category_name=category.name if category else "未知",
        author=created.author,
        views=created.views,
        publish_time=created.publish_time,
        image=created.image,
    )
    return success_response(payload, message="新闻发布成功")


@router.put("/{news_id}", response_model=ApiResponse[NewsDetailOut])
async def update_news(
    news_id: int,
    news_in: NewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="用户未登录")

    db_news = await news_crud.get_news_by_id_plain(db, news_id)
    if not db_news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    editable_authors = {current_user.username}
    if current_user.nickname:
        editable_authors.add(current_user.nickname)
    if db_news.author not in editable_authors:
        raise HTTPException(status_code=403, detail="无权限编辑该新闻")

    category = await news_crud.get_category_by_id(db, news_in.category_id)
    if not category:
        raise HTTPException(status_code=404, detail=f"分类ID {news_in.category_id} 不存在")
    if category.name != news_in.category_name.strip():
        raise HTTPException(status_code=400, detail="分类ID与分类名称不匹配")

    old_category_id = db_news.category_id
    try:
        updated = await news_crud.update_news(db, db_news, news_in, category_id=news_in.category_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    try:
        list_keys = await redis_client.keys(f"{NEWS_LIST_CACHE_KEY_PREFIX}:*")
        if list_keys:
            await redis_client.delete(*list_keys)

        affected_categories = {old_category_id, updated.category_id}
        for cat_id in affected_categories:
            category_keys = await redis_client.keys(f"{CATEGORY_NEWS_CACHE_KEY_PREFIX}:{cat_id}:*")
            if category_keys:
                await redis_client.delete(*category_keys)
    except Exception as exc:
        logger.warning("cache clear failed after update news id=%s, error=%s", updated.id, exc)

    payload = NewsDetailOut(
        id=updated.id,
        title=updated.title,
        description=updated.description,
        content=updated.content,
        category_id=updated.category_id,
        category_name=category.name,
        author=updated.author,
        views=updated.views,
        publish_time=updated.publish_time,
        image=updated.image,
    )
    return success_response(payload, message="新闻更新成功")


@router.delete("/{news_id}", response_model=ApiResponse[None])
async def delete_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="用户未登录")

    db_news = await news_crud.get_news_by_id_plain(db, news_id)
    if not db_news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    editable_authors = {current_user.username}
    if current_user.nickname:
        editable_authors.add(current_user.nickname)
    if db_news.author not in editable_authors:
        raise HTTPException(status_code=403, detail="无权限删除该新闻")

    category_id = db_news.category_id
    try:
        await news_crud.delete_news(db, db_news)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    try:
        list_keys = await redis_client.keys(f"{NEWS_LIST_CACHE_KEY_PREFIX}:*")
        if list_keys:
            await redis_client.delete(*list_keys)

        category_keys = await redis_client.keys(f"{CATEGORY_NEWS_CACHE_KEY_PREFIX}:{category_id}:*")
        if category_keys:
            await redis_client.delete(*category_keys)
    except Exception as exc:
        logger.warning("cache clear failed after delete news id=%s, error=%s", news_id, exc)

    return success_response(None, message="新闻删除成功")

# TODO: Implement news-related endpoints here
# 现在返回值必须指定为 ApiResponse[具体类型]，以便前端能正确解析 data 字段里的内容。
@router.get("/", response_model=ApiResponse[PaginatedData[NewsListItemOut]])
async def get_news(page: int = 1, size: int = 10, db: AsyncSession = Depends(get_db)):
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    skip = (safe_page - 1) * safe_size

    # Cache-Aside：先查缓存，命中直接返回，未命中再查数据库。
    cache_key = build_news_list_cache_key(safe_page, safe_size)
    redis_available, cached_payload = await read_json_cache(cache_key)
    if cached_payload:
        return paginated_response(
            cached_payload["items"],
            cached_payload["total"],
            cached_payload["page"],
            cached_payload["size"],
            message="List of news articles",
        )

    total = await news_crud.get_news_count(db)
    items = await news_crud.get_news(db, skip=skip, limit=safe_size)
    
    news_data = []
    for n in items:
        news_data.append(
            NewsListItemOut(
                id=n.id,
                title=n.title,
                description=n.description if n.description else (n.content[:100] + "..." if n.content else ""),
                category_name=n.category.name if n.category else "未知",
                author=n.author,
                views=n.views,
                publish_time=n.publish_time,
                image=n.image,
            )
        )

    # 缓存分页完整结果，避免下次请求再次执行 count + list 两次查询。
    cache_payload = {
        "items": [json.loads(item.json()) for item in news_data],
        "total": total,
        "page": safe_page,
        "size": safe_size,
    }
    list_ttl = LIST_CACHE_EMPTY_TTL_SECONDS if not news_data else NEWS_LIST_CACHE_TTL_SECONDS + random.randint(0, 20)
    await write_json_cache(cache_key, cache_payload, list_ttl, redis_available)

    return paginated_response(news_data, total, safe_page, safe_size, message="List of news articles")

@router.get("/hot", response_model=ApiResponse[list[HotNewsItemOut]])
async def get_hot_news(
    min_views: int = 5000,  # 浏览量阈值
    page: int = 1,          # 当前是第几批（用于换一换）
    size: int = 8,          # 此批次条数
    db: AsyncSession = Depends(get_db)
):
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    safe_min_views = max(0, min_views)
    skip = (safe_page - 1) * safe_size

    redis_available = True

    cache_key = build_hot_cache_key(safe_min_views, safe_page, safe_size)

    # 1) 先查缓存（命中即返回）
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            try:
                cached_data = json.loads(cached)
                return success_response(cached_data, message="success")
            except json.JSONDecodeError:
                logger.warning("hot cache decode failed, deleting bad key=%s", cache_key)
                try:
                    await redis_client.delete(cache_key)
                except Exception as delete_exc:
                    logger.warning("hot cache delete failed, key=%s, error=%s", cache_key, delete_exc)
    except Exception as exc:
        redis_available = False
        logger.warning("hot cache read failed, key=%s, error=%s", cache_key, exc)

    # 2) 缓存未命中，查数据库
    hot_list = await news_crud.get_hot_news(
        db,
        min_views=safe_min_views,
        limit=safe_size,
        offset=skip,
    )

    result_list = [
        {
            "id": news.id,
            "title": news.title,
            "views": news.views,
        }
        for news in hot_list
    ]

    # 3) 回填缓存（失败不影响主流程）
    if redis_available:
        try:
            ttl = HOT_CACHE_EMPTY_TTL_SECONDS if not result_list else HOT_CACHE_TTL_SECONDS + random.randint(0, 20)
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result_list, ensure_ascii=False),
            )
            logger.info("hot cache write succeeded, key=%s", cache_key)
        except Exception as exc:
            logger.warning("hot cache write failed, key=%s, error=%s", cache_key, exc)

    if not result_list and safe_page > 1:
        return success_response([], message="reached_end")

    return success_response(result_list, message="success")

# Todo: Implement "get_news_by_id" endpoint here
@router.get("/detail/{news_id}", response_model=ApiResponse[NewsDetailOut],)
async def get_news_by_id(
    news_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):

# 先增加权限校验，确保只有登录用户才能访问新闻详情接口。之后再查询新闻详情并返回。
    if not current_user:
        raise HTTPException(status_code=401, detail="用户未登录")

    news = await news_crud.get_news_by_id(db, news_id=news_id)
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    await db.commit()
        
    news_data = NewsDetailOut(
        id=news.id,
        title=news.title,
        description=news.description,
        content=news.content,
        category_id=news.category_id,
        category_name=news.category.name if news.category else "未知",
        author=news.author,
        views=news.views,
        publish_time=news.publish_time,
        image=news.image,
    )
        
    return success_response(news_data, message="Single news article")

# TODO: Implement "get_categories" endpoint here
@router.get("/categories", response_model=ApiResponse[list[CategoryOut]])
async def get_categories(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    # 分类列表更新频率较低，适合长 TTL 缓存。
    cache_key = build_category_list_cache_key(safe_skip, safe_limit)
    redis_available, cached_payload = await read_json_cache(cache_key)
    if cached_payload is not None:
        return success_response(cached_payload, message="List of news categories")

    categories = await news_crud.get_categories(db, skip=safe_skip, limit=safe_limit)
    category_data = [CategoryOut.from_orm(c) for c in categories]

    category_payload = [item.dict() for item in category_data]
    category_ttl = LIST_CACHE_EMPTY_TTL_SECONDS if not category_payload else CATEGORY_LIST_CACHE_TTL_SECONDS + random.randint(0, 30)
    await write_json_cache(cache_key, category_payload, category_ttl, redis_available)

    return success_response(category_data, message="List of news categories")

# TODO: Implement "get_news_by_categories" endpoint here
@router.get("/categories/{category_id}/news", response_model=ApiResponse[PaginatedData[NewsListItemOut]])
async def get_news_by_categories(category_id: int, page: int = 1, size: int = 10, db: AsyncSession = Depends(get_db)):
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    skip = (safe_page - 1) * safe_size

    # 这是分类维度分页查询，参数组合固定后非常适合做 key 缓存。
    cache_key = build_category_news_cache_key(category_id, safe_page, safe_size)
    redis_available, cached_payload = await read_json_cache(cache_key)
    if cached_payload:
        return paginated_response(
            cached_payload["items"],
            cached_payload["total"],
            cached_payload["page"],
            cached_payload["size"],
            message="List of news articles by category",
        )

    total = await news_crud.get_news_count_by_category(db, category_id=category_id)
    items = await news_crud.get_news_by_category(db, category_id=category_id, skip=skip, limit=safe_size)

    news_data = []
    for n in items:
        news_data.append(
            NewsListItemOut(
                id=n.id,
                title=n.title,
                description=n.description if n.description else (n.content[:100] + "..." if n.content else ""),
                category_name=n.category.name if n.category else "未知",
                author=n.author,
                views=n.views,
                publish_time=n.publish_time,
                image=n.image,
            )
        )

    category_news_payload = {
        "items": [item.dict() for item in news_data],
        "total": total,
        "page": safe_page,
        "size": safe_size,
    }
    category_news_ttl = LIST_CACHE_EMPTY_TTL_SECONDS if not news_data else CATEGORY_NEWS_CACHE_TTL_SECONDS + random.randint(0, 20)
    await write_json_cache(cache_key, category_news_payload, category_news_ttl, redis_available)

    return paginated_response(news_data, total, safe_page, safe_size, message="List of news articles by category")


