from sqlalchemy import Column, ForeignKey, Index, Integer, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from models.news import Base


class Like(Base):
    __tablename__ = "news_like"
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="uq_like_user_news"),
        Index("idx_like_user_id", "user_id"),
        Index("idx_like_news_id", "news_id"),
        Index("idx_like_user_created", "user_id", "created_at"),
        {"comment": "点赞表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="点赞ID")
    user_id = Column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    news_id = Column(
        MYSQL_INTEGER(unsigned=True),
        ForeignKey("news.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="新闻ID",
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="点赞时间")
    updated_at = None

    user = relationship("User")
    news = relationship("News")
