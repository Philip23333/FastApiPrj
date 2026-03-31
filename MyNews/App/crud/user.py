from sqlalchemy import select
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.user import UserCreate, UserUpdate

# 获取所有用户
async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

# 获取单个用户 (通过 ID)
async def get_user_by_id(db: AsyncSession, user_id: int):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

# 获取单个用户 (通过用户名)
async def get_user_by_username(db: AsyncSession, username: str):
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()

# 创建用户
async def create_user(db: AsyncSession, user: UserCreate):
    # 此处假设密码已经在注册逻辑处加密或等下会在传入前修改为哈希值
    db_user = User(**user.dict())
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user

# 更新用户
async def update_user(db: AsyncSession, user_id: int, user_update: UserUpdate):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None
    for key, value in user_update.dict(exclude_unset=True).items():
        setattr(db_user, key, value)
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user

# 删除用户
async def delete_user(db: AsyncSession, user_id: int):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return False
    await db.delete(db_user)
    return True


