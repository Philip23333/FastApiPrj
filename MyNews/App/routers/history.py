from dependencies.auth import get_current_user
from models.user import User
from crud import history as history_crud
from config.db_config import get_db
from fastapi import APIRouter, Depends, HTTPException
from schemas.history import HistoryListItemOut
from utils.response import paginated_response, success_response, ApiResponse, PaginatedData

router = APIRouter(
    prefix="/history",
    tags=["history"],
)

# 获取用户历史记录列表
@router.get("/", summary="获取用户历史记录列表", response_model=ApiResponse[PaginatedData[HistoryListItemOut]])
async def get_history(
    page: int = 1,
    size: int = 10,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_page = max(1, page)
    safe_size = max(1, min(size, 50))
    skip = (safe_page - 1) * safe_size
    total = await history_crud.get_history_count_by_user(db, user_id=current_user.id)
    items = await history_crud.get_history_by_user(db, user_id=current_user.id, offset=skip, limit=safe_size)

    history_data = []

    for i in items:
        history_data.append(
            HistoryListItemOut(
                id=i.id,
                user_id=i.user_id,
                news_id=i.news_id,
                created_at=i.created_at,
                updated_at=i.updated_at,
                view_time=i.view_time,
            )
        )
    return paginated_response(history_data, total, safe_page, safe_size, message="用户历史记录列表")

# 添加历史记录
@router.post("/{news_id}", summary="添加历史记录", response_model=ApiResponse[None])
async def create_history(
    news_id: int,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    
    await history_crud.upsert_history_record(db, user_id=current_user.id, news_id=news_id)
    await db.commit()
    return success_response(None, message="历史记录添加成功")

# 删除历史记录
@router.delete("/{news_id}", summary="删除历史记录", response_model=ApiResponse[None])
async def delete_history(news_id: int, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    res = await history_crud.delete_history_record(db, user_id=current_user.id, news_id=news_id)
    if res:
        await db.commit()
        return success_response(None, message="删除历史记录成功")
    raise HTTPException(status_code=404, detail="未找到历史记录")