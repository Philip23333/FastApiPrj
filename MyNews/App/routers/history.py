from dependencies.auth import get_current_user
from models.user import User
from crud import history as history_crud
from crud import news as news_crud
from config.db_config import get_db
from fastapi import APIRouter, Depends, HTTPException
from schemas.history import HistoryListItemOut
from utils.response import paginated_response, success_response, ApiResponse, PaginatedData
from utils.pagination import normalize_pagination

router = APIRouter(
    prefix="/history",
    tags=["history"],
)

@router.get("/", summary="获取用户历史记录列表", response_model=ApiResponse[PaginatedData[HistoryListItemOut]])
async def get_history(
    page: int = 1,
    size: int = 10,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页读取当前用户历史记录，并对下架新闻做降级展示。"""
    safe_page, safe_size, skip = normalize_pagination(page, size, max_size=50)
    total = await history_crud.get_history_count_by_user(db, user_id=current_user.id)
    items = await history_crud.get_history_by_user(db, user_id=current_user.id, offset=skip, limit=safe_size)

    history_data = []

    for i in items:
        news = i.news
        is_removed = bool(news is None or news.is_deleted or news.audit_status == "rejected")
        history_data.append(
            HistoryListItemOut(
                id=i.id,
                user_id=i.user_id,
                news_id=i.news_id,
                title="新闻已下架" if is_removed else (news.title if news else "新闻已下架"),
                description="该新闻已下架，暂不可查看详情。" if is_removed else (news.description if news else None),
                category_name="-" if is_removed else (news.category.name if news and news.category else "未知"),
                views=0 if is_removed else (news.views if news else 0),
                image=None if is_removed else (news.image if news else None),
                is_removed=is_removed,
                created_at=i.created_at,
                updated_at=i.updated_at,
                view_time=i.view_time,
            )
        )
    return paginated_response(history_data, total, safe_page, safe_size, message="用户历史记录列表")

@router.post("/{news_id}", summary="添加历史记录", response_model=ApiResponse[None])
async def create_history(
    news_id: int,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增或更新浏览历史时间戳。"""
    news = await news_crud.get_news_by_id_plain(db, news_id)
    if not news or news.is_deleted or news.audit_status == "rejected":
        raise HTTPException(status_code=404, detail="新闻已下架")
    
    await history_crud.upsert_history_record(db, user_id=current_user.id, news_id=news_id)
    await db.commit()
    return success_response(None, message="历史记录添加成功")

@router.delete("/{news_id}", summary="删除历史记录", response_model=ApiResponse[None])
async def delete_history(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除指定新闻的浏览历史记录。"""
    res = await history_crud.delete_history_record(db, user_id=current_user.id, news_id=news_id)
    if res:
        await db.commit()
        return success_response(None, message="删除历史记录成功")
    raise HTTPException(status_code=404, detail="未找到历史记录")