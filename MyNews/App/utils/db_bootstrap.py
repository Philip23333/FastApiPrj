from sqlalchemy import text

from models.ai_chat import AIChatHistory, AIUserMemory
from models.comment import Comment
from models.like import Like


async def _ensure_news_column(conn, column_name: str, ddl_sql: str):
    exists_res = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'news'
              AND COLUMN_NAME = :column_name
            LIMIT 1
            """
        ),
        {"column_name": column_name},
    )
    if exists_res.scalar_one_or_none() is None:
        await conn.execute(text(ddl_sql))


async def _ensure_comment_column(conn, column_name: str, ddl_sql: str):
    exists_res = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'news_comment'
              AND COLUMN_NAME = :column_name
            LIMIT 1
            """
        ),
        {"column_name": column_name},
    )
    if exists_res.scalar_one_or_none() is None:
        await conn.execute(text(ddl_sql))


async def ensure_db_bootstrap(async_engine):
    # 启动时补齐 AI/点赞/评论相关表，以及新闻冗余计数字段。
    async with async_engine.begin() as conn:
        await conn.run_sync(AIChatHistory.__table__.create, checkfirst=True)
        await conn.run_sync(AIUserMemory.__table__.create, checkfirst=True)
        await conn.run_sync(Like.__table__.create, checkfirst=True)
        await conn.run_sync(Comment.__table__.create, checkfirst=True)

        await _ensure_comment_column(
            conn,
            "parent_comment_id",
            "ALTER TABLE news_comment ADD COLUMN parent_comment_id INT UNSIGNED NULL COMMENT '父评论ID'",
        )

        await _ensure_news_column(
            conn,
            "like_count",
            "ALTER TABLE news ADD COLUMN like_count INT NOT NULL DEFAULT 0 COMMENT '点赞数'",
        )
        await _ensure_news_column(
            conn,
            "comment_count",
            "ALTER TABLE news ADD COLUMN comment_count INT NOT NULL DEFAULT 0 COMMENT '评论数'",
        )
