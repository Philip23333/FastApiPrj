from dependencies.auth import get_current_user
from models.user import User
from schemas.favorite import FavoritesListItemOut
from crud import favorite as favorite_crud
from config.db_config import get_db
from fastapi import APIRouter, Depends, HTTPException
from utils.response import paginated_response, success_response, ApiResponse, PaginatedData

router = APIRouter(
    prefix="/favorites",
    tags=["favorites"],
)

# 获取用户收藏列表
@router.get("/", summary="获取用户收藏列表", response_model=ApiResponse[PaginatedData[FavoritesListItemOut]])
async def get_favorites(
    page: int = 1,
    size: int = 10,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    skip = (safe_page - 1) * safe_size
    total = await favorite_crud.get_favorites_count_by_user(db, user_id=current_user.id)
    items = await favorite_crud.get_favorites_by_user(db, user_id=current_user.id, offset=skip, limit=safe_size)

    favorites_data = []

    for i in items:
        favorites_data.append(
            FavoritesListItemOut(
                id=i.id,
                user_id=i.user_id,
                news_id=i.news_id,
                created_at=i.created_at,
            )
        )
    return paginated_response(favorites_data, total, safe_page, safe_size, message="用户收藏列表")

# 收藏新闻
@router.post("/{news_id}", summary="收藏新闻", response_model=ApiResponse[None])
async def create_favorite(
    news_id: int,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not await favorite_crud.news_exists(db, news_id=news_id):
        raise HTTPException(status_code=404, detail="新闻不存在")

    if await favorite_crud.is_favorited(db, user_id=current_user.id, news_id=news_id):
        return success_response(None, message="新闻已收藏")

    await favorite_crud.create_favorite(db, user_id=current_user.id, news_id=news_id)
    await db.commit()
    return success_response(None, message="收藏成功")

# 取消收藏
@router.delete("/{news_id}", summary="取消收藏", response_model=ApiResponse[None])
async def delete_favorite(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    res = await favorite_crud.delete_favorite(db, user_id=current_user.id, news_id=news_id)
    if res:
        await db.commit()
        return success_response(None, message="取消收藏成功")
    raise HTTPException(status_code=404, detail="未找到收藏记录")

# 获取用户是否收藏了某条新闻
@router.get("/check/{news_id}", summary="检查是否收藏", response_model=ApiResponse[bool])
async def check_favorite(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    is_favorited = await favorite_crud.is_favorited(db, user_id=current_user.id, news_id=news_id)
    return success_response(is_favorited, message="检查收藏状态")
