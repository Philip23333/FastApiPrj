from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_config import get_db
from dependencies.auth import get_current_admin_user, get_current_user
from crud import user
from models.user import User
from schemas.user import LoginTokenData, UserAdminCreate, UserAdminRoleUpdate, UserAdminStatusUpdate, UserAdminUpdate, UserCreate, UserOut, UserUpdate, UserLogin
from utils.jwt_auth import create_access_token
from utils.security import hash_password, verify_password, is_hashed_password
from utils.response import ApiResponse, PaginatedData, created_response, paginated_response, success_response

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


def _guard_admin_self_action(current_user_id: int, target_user_id: int, *, action: str):
    """阻止管理员对自己执行危险操作，避免后台入口被锁死。"""
    if current_user_id != target_user_id:
        return

    message_map = {
        "delete": "不能删除自己",
        "disable": "不能禁用自己",
        "demote": "不能修改自己的管理员角色",
    }
    raise HTTPException(status_code=400, detail=message_map.get(action, "不允许操作自己"))


# 默认只有管理员可以访问以下接口，后续可根据需求调整权限控制逻辑。
@router.get("/admin", response_model=ApiResponse[List[UserOut]])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员查看用户列表。"""
    _ = current_admin_user
    users = await user.get_users(db, skip=skip, limit=limit)
    return success_response([UserOut.from_orm(u) for u in users], message="List of users")


@router.get("/admin/{user_id}", response_model=ApiResponse[UserOut])
async def admin_read_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员查看单个用户详情。"""
    _ = current_admin_user
    db_user = await user.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success_response(UserOut.from_orm(db_user), message="管理员查看用户详情")


@router.put("/admin/{user_id}", response_model=ApiResponse[UserOut])
async def admin_update_user(
    user_id: int,
    user_in: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员更新用户信息（含角色与状态字段）。"""
    _ = current_admin_user
    # 关键校验：更新手机号前先做唯一性检查，避免数据库唯一索引冲突。
    if user_in.phone and await user.exists_phone(db, user_in.phone, exclude_user_id=user_id):
        raise HTTPException(status_code=400, detail="手机号已被注册")

    update_payload = user_in
    if user_in.password is not None:
        update_payload.password = hash_password(user_in.password)

    try:
        db_user = await user.update_user(
            db,
            user_id,
            update_payload,
            allow_privileged_fields=True,
        )
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        await db.commit()
        return success_response(UserOut.from_orm(db_user), message="管理员更新用户成功")
    except DataError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="请求字段值不合法，请检查枚举字段取值") from exc


@router.patch("/admin/{user_id}/role", response_model=ApiResponse[UserOut])
async def admin_update_user_role(
    user_id: int,
    payload: UserAdminRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员更新目标用户角色。"""
    if payload.role != "admin":
        _guard_admin_self_action(current_admin_user.id, user_id, action="demote")

    db_user = await user.set_user_role(db, user_id=user_id, role=payload.role)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await db.commit()
    return success_response(UserOut.from_orm(db_user), message="用户角色更新成功")


@router.patch("/admin/{user_id}/status", response_model=ApiResponse[UserOut])
async def admin_update_user_status(
    user_id: int,
    payload: UserAdminStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员更新目标用户状态。"""
    if payload.status != "active":
        _guard_admin_self_action(current_admin_user.id, user_id, action="disable")

    db_user = await user.set_user_status(db, user_id=user_id, status=payload.status)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await db.commit()
    return success_response(UserOut.from_orm(db_user), message="用户状态更新成功")


@router.delete("/admin/{user_id}", response_model=ApiResponse[None])
async def admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
):
    """管理员删除指定用户。"""
    _guard_admin_self_action(current_admin_user.id, user_id, action="delete")

    success = await user.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    await db.commit()
    return success_response(None, message="管理员删除用户成功")


@router.post("/token")
async def issue_oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Swagger OAuth2 password flow 使用的标准 token 端点。"""
    db_user = await user.get_user_by_username(db, username=form_data.username)
    if not db_user or not verify_password(form_data.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if db_user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    need_upgrade_password = not is_hashed_password(db_user.password)
    if need_upgrade_password:
        db_user.password = hash_password(form_data.password)

    access_token, expires_in = create_access_token(db_user.id, db_user.username)

    if need_upgrade_password:
        await db.commit()

    # OAuth2 标准字段，Swagger 会自动将 access_token 注入 Bearer 头。
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


# 返回值必须指定为 ApiResponse[具体类型]，以便前端能正确解析 data 字段里的内容。
@router.post("/login", response_model=ApiResponse[LoginTokenData])
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户名密码登录并签发访问令牌。"""
    db_user = await user.get_user_by_username(db, username=user_in.username)
    # user_in.password 传入的明文, db_user.password 数据库中存储的哈希值或者明文（如果是旧数据）
    if not db_user or not verify_password(user_in.password, db_user.password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 关键校验：禁用账号不允许登录。
    if db_user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

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
    """注册用户并将密码以哈希方式存储。"""
    # 检查用户名是否已存在，改造注册逻辑:复制请求体并哈希化密码后入库，确保新用户密码不会明文落库。
    db_user = await user.get_user_by_username(db, username=user_in.username)
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已被注册")
    if user_in.phone and await user.exists_phone(db, user_in.phone):
        raise HTTPException(status_code=400, detail="手机号已被注册")
    user_payload = user_in.dict()
    user_payload["password"] = hash_password(user_in.password)

    created_user = await user.create_user(db=db, user=UserCreate(**user_payload))
    await db.commit()
    return created_response(UserOut.from_orm(created_user), message="注册成功")

@router.get("/{user_id}", response_model=ApiResponse[UserOut])
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """按用户 ID 读取公开资料。"""
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
    """用户更新自己的资料信息。"""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="无权限操作该用户")

    # 关键保护：普通用户接口禁止修改 role/status，发现即拒绝。
    if user_in.role is not None or user_in.status is not None:
        raise HTTPException(status_code=403, detail="无权限修改角色或状态")

    if user_in.phone and await user.exists_phone(db, user_in.phone, exclude_user_id=user_id):
        raise HTTPException(status_code=400, detail="手机号已被注册")

    # 更新时先复制请求体，再把 password 替换为 hash_password 结果。之后再调用 create_user 入库，确保新用户密码不会明文落库。 
    if user_in.password is not None:
        user_in.password = hash_password(user_in.password)
    db_user = await user.update_user(db, user_id, user_in)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.commit()
    return success_response(UserOut.from_orm(db_user), message="User updated successfully")
