from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker,AsyncSession


# Database URL
ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/news_app?charset=utf8mb4" 
POOL_SIZE = 10
MAX_OVERFLOW = 20
# Create engine
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,# 数据库连接URL
    echo = True,# 是否输出SQL语句日志，默认为False
    pool_size=POOL_SIZE, # 连接池的大小，默认为5
    max_overflow=MAX_OVERFLOW,# 连接池的最大溢出数量，超过这个数量的连接将被拒绝
)

# Create session
AsyncSessionLocal = async_sessionmaker(
    class_ = AsyncSession, # 使用异步会话类
    bind=async_engine, # 绑定引擎
    expire_on_commit=False, # 提交后不自动过期对象，默认为True
)

# Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback() # 回滚事务
            raise
        finally:
            await session.close() # 关闭会话