from sqlalchemy import Column, ForeignKey, Index, Integer, Text, TIMESTAMP, text
from sqlalchemy.dialects.mysql import INTEGER as MYSQL_INTEGER
from sqlalchemy.orm import relationship

from models.news import Base


class Comment(Base):
    __tablename__ = "news_comment"
    __table_args__ = (
        Index("idx_comment_news_created", "news_id", "created_at"),
        Index("idx_comment_user_created", "user_id", "created_at"),
        {"comment": "评论表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="评论ID")
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
    content = Column(Text, nullable=False, comment="评论内容")
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="评论时间")
    updated_at = None

    user = relationship("User")
    news = relationship("News")
