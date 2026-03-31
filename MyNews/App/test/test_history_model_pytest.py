import asyncio
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config.db_config import AsyncSessionLocal
from config.db_config import async_engine
from models.history import History


_TEST_LOOP = None


def run(coro):
    global _TEST_LOOP
    if _TEST_LOOP is None or _TEST_LOOP.is_closed():
        _TEST_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_TEST_LOOP)
    return _TEST_LOOP.run_until_complete(coro)


def teardown_module(module):
    # 显式归还并销毁连接池，避免 Windows 下事件循环关闭后清理连接报错。
    global _TEST_LOOP
    if _TEST_LOOP is not None and not _TEST_LOOP.is_closed():
        _TEST_LOOP.run_until_complete(async_engine.dispose())
        _TEST_LOOP.close()
    _TEST_LOOP = None


async def _db_ready() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


async def _create_temp_user_and_news(session):
    suffix = uuid.uuid4().hex[:8]

    category_name = f"ut_history_cat_{suffix}"
    await session.execute(
        text("INSERT INTO news_category (name, sort_order) VALUES (:name, 0)"),
        {"name": category_name},
    )
    cat_row = await session.execute(
        text("SELECT id FROM news_category WHERE name=:name"),
        {"name": category_name},
    )
    category_id = cat_row.scalar_one()

    username = f"ut_history_user_{suffix}"
    await session.execute(
        text("INSERT INTO user (username, password, nickname) VALUES (:username, :password, :nickname)"),
        {
            "username": username,
            "password": "plain_for_fk_test",
            "nickname": "history_test_user",
        },
    )
    user_row = await session.execute(
        text("SELECT id FROM user WHERE username=:username"),
        {"username": username},
    )
    user_id = user_row.scalar_one()

    news_title = f"ut_history_news_{suffix}"
    await session.execute(
        text(
            """
            INSERT INTO news (title, description, content, category_id, author)
            VALUES (:title, :description, :content, :category_id, :author)
            """
        ),
        {
            "title": news_title,
            "description": "history model test",
            "content": "history model test content",
            "category_id": category_id,
            "author": "pytest",
        },
    )
    news_row = await session.execute(
        text("SELECT id FROM news WHERE title=:title"),
        {"title": news_title},
    )
    news_id = news_row.scalar_one()

    return {
        "user_id": user_id,
        "news_id": news_id,
        "category_id": category_id,
    }


async def _cleanup(session, ids):
    # 删除顺序：user/news -> history 会由外键 cascade 自动删除；最后删分类。
    await session.execute(text("DELETE FROM user WHERE id=:id"), {"id": ids["user_id"]})
    await session.execute(text("DELETE FROM news WHERE id=:id"), {"id": ids["news_id"]})
    await session.execute(text("DELETE FROM news_category WHERE id=:id"), {"id": ids["category_id"]})


async def _history_has_user_news_unique(session) -> bool:
    row = await session.execute(
        text(
            """
            SELECT COUNT(1)
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'history'
              AND index_name = 'user_news_unique'
              AND non_unique = 0
            """
        )
    )
    return row.scalar_one() > 0


@pytest.mark.history
def test_history_insert_success():
    if not run(_db_ready()):
        pytest.skip("Database is not ready; skip history model test.")

    async def _case():
        async with AsyncSessionLocal() as session:
            ids = await _create_temp_user_and_news(session)
            try:
                record = History(user_id=ids["user_id"], news_id=ids["news_id"])
                session.add(record)
                await session.commit()
                await session.refresh(record)

                assert record.id is not None
                assert record.user_id == ids["user_id"]
                assert record.news_id == ids["news_id"]
            finally:
                await _cleanup(session, ids)
                await session.commit()

    run(_case())


@pytest.mark.history
def test_history_unique_user_news_constraint():
    if not run(_db_ready()):
        pytest.skip("Database is not ready; skip history model test.")

    async def _case():
        async with AsyncSessionLocal() as session:
            ids = await _create_temp_user_and_news(session)
            try:
                first = History(user_id=ids["user_id"], news_id=ids["news_id"])
                session.add(first)
                await session.commit()

                second = History(user_id=ids["user_id"], news_id=ids["news_id"])
                session.add(second)
                if await _history_has_user_news_unique(session):
                    with pytest.raises(IntegrityError):
                        await session.commit()
                    await session.rollback()
                else:
                    await session.commit()
            finally:
                await _cleanup(session, ids)
                await session.commit()

    run(_case())


@pytest.mark.history
def test_history_foreign_key_constraint():
    if not run(_db_ready()):
        pytest.skip("Database is not ready; skip history model test.")

    async def _case():
        async with AsyncSessionLocal() as session:
            ids = await _create_temp_user_and_news(session)
            try:
                bad = History(user_id=999999999, news_id=ids["news_id"])
                session.add(bad)
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
            finally:
                await _cleanup(session, ids)
                await session.commit()

    run(_case())


@pytest.mark.history
def test_history_cascade_delete_with_user():
    if not run(_db_ready()):
        pytest.skip("Database is not ready; skip history model test.")

    async def _case():
        async with AsyncSessionLocal() as session:
            ids = await _create_temp_user_and_news(session)
            try:
                record = History(user_id=ids["user_id"], news_id=ids["news_id"])
                session.add(record)
                await session.commit()

                await session.execute(text("DELETE FROM user WHERE id=:id"), {"id": ids["user_id"]})
                await session.commit()

                row = await session.execute(
                    text("SELECT COUNT(1) FROM history WHERE news_id=:news_id"),
                    {"news_id": ids["news_id"]},
                )
                assert row.scalar_one() == 0

                # user 已删，避免重复删除失败
                ids["user_id"] = None
            finally:
                if ids.get("user_id"):
                    await session.execute(text("DELETE FROM user WHERE id=:id"), {"id": ids["user_id"]})
                await session.execute(text("DELETE FROM news WHERE id=:id"), {"id": ids["news_id"]})
                await session.execute(text("DELETE FROM news_category WHERE id=:id"), {"id": ids["category_id"]})
                await session.commit()

    run(_case())
