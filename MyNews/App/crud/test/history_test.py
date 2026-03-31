import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from crud import history as history_crud
from config.db_config import AsyncSessionLocal, async_engine


async def main():
    try:
        async with AsyncSessionLocal() as db:
            record = await history_crud.create_history_record(db, 1, 1)
            await db.commit()
            print(f"history upsert success: id={record.id}, user_id={record.user_id}, news_id={record.news_id}")
    finally:
        # 显式释放连接池，避免解释器退出时事件循环已关闭引发 aiomysql 清理告警。
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())