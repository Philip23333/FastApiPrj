from sqlalchemy import Column, ForeignKey, Index, Integer, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.news import Base


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="user_news_unique"),
        Index("fk_favorite_user_idx", "user_id"),
        Index("fk_favorite_news_idx", "news_id"),
        {"comment": "收藏表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="收藏ID")
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    news_id = Column(
        Integer,
        ForeignKey("news.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="新闻ID",
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="收藏时间")
    updated_at = None

    # 仅在 Favorite 侧建立关系，避免要求 User/News 先声明 back_populates。
    user = relationship("User")
    news = relationship("News")

    def __repr__(self) -> str:
        return f"<Favorite(id={self.id}, user_id={self.user_id}, news_id={self.news_id})>"