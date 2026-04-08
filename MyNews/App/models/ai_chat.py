from sqlalchemy import Column, ForeignKey, Integer, Text, TIMESTAMP, func, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER

from models.news import Base


class AIChatHistory(Base):
    __tablename__ = "ai_chat_history"
    __table_args__ = (
        Index("idx_ai_chat_history_user_created", "user_id", "created_at"),
        {"comment": "AI问答历史表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, nullable=False, comment="AI回答")
    citations_json = Column(Text, nullable=True, comment="引用来源JSON")
    model = Column(Text, nullable=True, comment="模型名称")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = None


class AIUserMemory(Base):
    __tablename__ = "ai_user_memory"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ai_user_memory_user_id"),
        {"comment": "AI用户记忆表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记忆ID")
    user_id = Column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    memory_text = Column(Text, nullable=False, comment="用户长期记忆摘要")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    created_at = None