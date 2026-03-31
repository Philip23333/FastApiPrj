from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from dependencies.auth import get_current_user
from crud import user
from models.user import User
from schemas.user import LoginTokenData, UserCreate, UserOut, UserUpdate, UserLogin
from utils.jwt_auth import create_access_token
from utils.security import hash_password, verify_password, is_hashed_password
from utils.response import ApiResponse, success_response, created_response

router = APIRouter(
    prefix="/users",
    tags=["users"],
)
# 现在返回值必须指定为 ApiResponse[具体类型]，以便前端能正确解析 data 字段里的内容。
@router.post("/login", response_model=ApiResponse[LoginTokenData])
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    db_user = await user.get_user_by_username(db, username=user_in.username)
    # user_in.password 传入的明文, db_user.password 数据库中存储的哈希值或者明文（如果是旧数据）
    if not db_user or not verify_password(user_in.password, db_user.password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 兼容历史明文密码：本次登录成功后升级为哈希存储。
    need_upgrade_password = not is_hashed_password(db_user.password)
    if need_upgrade_password:
        db_user.password = hash_password(user_in.password)

    access_token, expires_in = create_access_token(db_user.id, db_user.username)
    token_data = LoginTokenData(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserOut.from_orm(db_user),
    )

    if need_upgrade_password:
        await db.commit()

    return success_response(token_data, message="登录成功")

@router.post("/register", response_model=ApiResponse[UserOut], status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # 检查用户名是否已存在，改造注册逻辑:复制请求体并哈希化密码后入库，确保新用户密码不会明文落库。
    db_user = await user.get_user_by_username(db, username=user_in.username)
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已被注册")
    user_payload = user_in.dict()
    user_payload["password"] = hash_password(user_in.password)

    created_user = await user.create_user(db=db, user=UserCreate(**user_payload))
    await db.commit()
    return created_response(UserOut.from_orm(created_user), message="注册成功")

@router.get("/", response_model=ApiResponse[List[UserOut]])
async def get_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    users = await user.get_users(db, skip=skip, limit=limit)
    
    return success_response([UserOut.from_orm(u) for u in users], message="List of users")

@router.get("/{user_id}", response_model=ApiResponse[UserOut])
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    db_user = await user.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success_response(UserOut.from_orm(db_user), message="User details")

@router.put("/{user_id}", response_model=ApiResponse[UserOut])
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权限操作该用户")

    # 更新时先复制请求体，再把 password 替换为 hash_password 结果。之后再调用 create_user 入库，确保新用户密码不会明文落库。 
    if user_in.password is not None:
        user_in.password = hash_password(user_in.password)
    db_user = await user.update_user(db, user_id, user_in)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return success_response(UserOut.from_orm(db_user), message="User updated successfully")

@router.delete("/{user_id}", response_model=ApiResponse[None])
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权限操作该用户")

    success = await user.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return success_response(None, message="User deleted successfully")