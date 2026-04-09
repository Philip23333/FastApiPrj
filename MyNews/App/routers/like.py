from fastapi import APIRouter, Depends, HTTPException

from config.db_config import get_db
from crud import like as like_crud
from crud import news as news_crud
from dependencies.auth import get_current_user
from models.user import User
from schemas.like import LikeListItemOut, NewsLikeSummaryOut
from utils.pagination import normalize_pagination
from utils.response import ApiResponse, PaginatedData, paginated_response, success_response

router = APIRouter(prefix="/likes", tags=["likes"])


@router.get("/", summary="获取用户点赞列表", response_model=ApiResponse[PaginatedData[LikeListItemOut]])
async def get_likes(
    page: int = 1,
    size: int = 10,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_page, safe_size, skip = normalize_pagination(page, size, max_size=50)
    total = await like_crud.get_likes_count_by_user(db, user_id=current_user.id)
    items = await like_crud.get_likes_by_user(db, user_id=current_user.id, offset=skip, limit=safe_size)

    payload = [
        LikeListItemOut(
            id=item.id,
            user_id=item.user_id,
            news_id=item.news_id,
            created_at=item.created_at,
        )
        for item in items
    ]
    return paginated_response(payload, total, safe_page, safe_size, message="用户点赞列表")


@router.get("/check/{news_id}", summary="检查是否点赞", response_model=ApiResponse[NewsLikeSummaryOut])
async def check_like(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    news = await news_crud.get_news_by_id_plain(db, news_id)
    if not news or news.is_deleted:
        raise HTTPException(status_code=404, detail="新闻不存在")

    is_liked = await like_crud.is_liked(db, user_id=current_user.id, news_id=news_id)
    return success_response(NewsLikeSummaryOut(like_count=news.like_count, is_liked=is_liked), message="检查点赞状态")


@router.post("/{news_id}", summary="点赞新闻", response_model=ApiResponse[NewsLikeSummaryOut])
async def create_like(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    news = await news_crud.get_news_by_id_plain(db, news_id)
    if not news or news.is_deleted or news.audit_status == "rejected":
        raise HTTPException(status_code=404, detail="新闻已下架")

    if not await like_crud.is_liked(db, user_id=current_user.id, news_id=news_id):
        await like_crud.create_like(db, user_id=current_user.id, news_id=news_id)
        await db.commit()
        news = await news_crud.get_news_by_id_plain(db, news_id)

    return success_response(
        NewsLikeSummaryOut(like_count=news.like_count if news else 0, is_liked=True),
        message="点赞成功",
    )


@router.delete("/{news_id}", summary="取消点赞", response_model=ApiResponse[NewsLikeSummaryOut])
async def delete_like(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = await like_crud.delete_like(db, user_id=current_user.id, news_id=news_id)
    if deleted:
        await db.commit()

    news = await news_crud.get_news_by_id_plain(db, news_id)
    like_count = news.like_count if news else 0
    return success_response(NewsLikeSummaryOut(like_count=like_count, is_liked=False), message="取消点赞成功")
