from fastapi import APIRouter, Depends, HTTPException

from config.db_config import get_db
from crud import comment as comment_crud
from crud import news as news_crud
from dependencies.auth import get_current_user
from models.user import User
from schemas.comment import CommentCreateIn, CommentMineItemOut, CommentNewsItemOut
from utils.pagination import normalize_pagination
from utils.response import ApiResponse, PaginatedData, paginated_response, success_response

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/news/{news_id}", summary="获取新闻评论列表", response_model=ApiResponse[PaginatedData[CommentNewsItemOut]])
async def get_comments_by_news(
    news_id: int,
    page: int = 1,
    size: int = 20,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    news = await news_crud.get_news_by_id_plain(db, news_id)
    if not news or news.is_deleted or news.audit_status == "rejected":
        raise HTTPException(status_code=404, detail="新闻已下架")

    safe_page, safe_size, skip = normalize_pagination(page, size, max_size=100)
    total = await comment_crud.get_comments_count_by_news(db, news_id=news_id)
    items = await comment_crud.get_comments_by_news(db, news_id=news_id, offset=skip, limit=safe_size)

    payload = [
        CommentNewsItemOut(
            id=item.id,
            news_id=item.news_id,
            user_id=item.user_id,
            username=item.user.username if item.user else "用户",
            nickname=item.user.nickname if item.user else None,
            content=item.content,
            parent_comment_id=item.parent_comment_id,
            created_at=item.created_at,
            replies=[],
        )
        for item in items
    ]
    return paginated_response(payload, total, safe_page, safe_size, message="新闻评论列表")


@router.get("/mine", summary="获取我的评论列表", response_model=ApiResponse[PaginatedData[CommentMineItemOut]])
async def get_my_comments(
    page: int = 1,
    size: int = 20,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_page, safe_size, skip = normalize_pagination(page, size, max_size=100)
    total = await comment_crud.get_comments_count_by_user(db, user_id=current_user.id)
    items = await comment_crud.get_comments_by_user(db, user_id=current_user.id, offset=skip, limit=safe_size)

    payload = [
        CommentMineItemOut(
            id=item.id,
            news_id=item.news_id,
            title=item.news.title if item.news else "新闻已下架",
            content=item.content,
            created_at=item.created_at,
        )
        for item in items
    ]
    return paginated_response(payload, total, safe_page, safe_size, message="我的评论列表")


@router.post("/{news_id}", summary="新增评论", response_model=ApiResponse[CommentNewsItemOut])
async def create_comment(
    news_id: int,
    comment_in: CommentCreateIn,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    news = await news_crud.get_news_by_id_plain(db, news_id)
    if not news or news.is_deleted or news.audit_status == "rejected":
        raise HTTPException(status_code=404, detail="新闻已下架")

    parent_comment_id = comment_in.parent_comment_id
    if parent_comment_id is not None:
        parent_comment = await comment_crud.get_comment_by_id(db, parent_comment_id)
        if not parent_comment or parent_comment.news_id != news_id:
            raise HTTPException(status_code=400, detail="父评论不存在或不属于当前新闻")

    item = await comment_crud.create_comment(
        db,
        user_id=current_user.id,
        news_id=news_id,
        content=comment_in.content.strip(),
        parent_comment_id=parent_comment_id,
    )
    await db.commit()

    payload = CommentNewsItemOut(
        id=item.id,
        news_id=item.news_id,
        user_id=item.user_id,
        username=current_user.username,
        nickname=current_user.nickname,
        content=item.content,
        parent_comment_id=item.parent_comment_id,
        created_at=item.created_at,
        replies=[],
    )
    return success_response(payload, message="评论成功")
