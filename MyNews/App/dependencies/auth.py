from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from crud import user as user_crud
from models.user import User
from utils.jwt_auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


def _ensure_active_user(user: User) -> User:
    """统一校验账号状态，禁用账号拒绝访问受保护接口。"""
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )
    return user

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """根据 Bearer Token 解析并返回当前用户。"""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    if sub is None:
        raise credentials_error

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise credentials_error from exc

    db_user = await user_crud.get_user_by_id(db, user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _ensure_active_user(db_user)

async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户为管理员。"""
    _ensure_active_user(current_user)

    # 关键校验：用户管理接口只允许 admin 角色访问。
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可执行该操作",
        )

    return current_user


async def get_current_reviewer_or_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户为审核员或管理员。"""
    _ensure_active_user(current_user)

    if current_user.role not in {"reviewer", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅审核员或管理员可执行该操作",
        )

    return current_user
