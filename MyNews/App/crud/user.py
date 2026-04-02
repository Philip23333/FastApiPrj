from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from schemas.user import UserCreate, UserUpdate


async def get_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
):
    """分页查询用户，兼容旧调用，同时支持后台管理筛选。"""
    stmt = select(User)

    # 关键筛选：支持用户名/昵称/手机号模糊检索，便于后台检索用户。
    if keyword:
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.like(pattern),
                User.nickname.like(pattern),
                User.phone.like(pattern),
            )
        )

    if role:
        stmt = stmt.where(User.role == role)

    if status:
        stmt = stmt.where(User.status == status)

    stmt = stmt.order_by(User.id.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_users(
    db: AsyncSession,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
):
    """统计用户总数（可配合同条件筛选用于后台分页）。"""
    stmt = select(func.count(User.id))

    if keyword:
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.like(pattern),
                User.nickname.like(pattern),
                User.phone.like(pattern),
            )
        )

    if role:
        stmt = stmt.where(User.role == role)

    if status:
        stmt = stmt.where(User.status == status)

    result = await db.execute(stmt)
    return result.scalar_one()


async def get_user_by_id(db: AsyncSession, user_id: int):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_by_username(db: AsyncSession, username: str):
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_by_phone(db: AsyncSession, phone: str):
    stmt = select(User).where(User.phone == phone)
    result = await db.execute(stmt)
    return result.scalars().first()


async def exists_username(
    db: AsyncSession,
    username: str,
    exclude_user_id: int | None = None,
):
    """检查用户名是否存在；可排除当前用户用于更新场景。"""
    stmt = select(User).where(User.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def exists_phone(
    db: AsyncSession,
    phone: str,
    exclude_user_id: int | None = None,
):
    """检查手机号是否存在；空手机号视为不冲突。"""
    if not phone:
        return False

    stmt = select(User).where(User.phone == phone)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def create_user(db: AsyncSession, user: UserCreate):
    # 关键保护：注册默认 user/active，避免外部传参注入高权限。
    payload = user.dict()
    payload.setdefault("role", "user")
    payload.setdefault("status", "active")

    db_user = User(**payload)
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user


async def update_user(
    db: AsyncSession,
    user_id: int,
    user_update: UserUpdate,
    allow_privileged_fields: bool = False,
):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_update.dict(exclude_unset=True)

    # 关键保护：普通更新默认禁止改 role/status，防止越权提权。
    if not allow_privileged_fields:
        update_data.pop("role", None)
        update_data.pop("status", None)

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user


async def set_user_role(db: AsyncSession, user_id: int, role: str):
    """后台专用：更新用户角色。"""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None

    db_user.role = role
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user


async def set_user_status(db: AsyncSession, user_id: int, status: str):
    """后台专用：启用/禁用用户账号。"""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None

    db_user.status = status
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user


async def delete_user(db: AsyncSession, user_id: int):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return False
    await db.delete(db_user)
    return True


