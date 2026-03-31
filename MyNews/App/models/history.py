
from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from models.news import Base
from models.news import News
from models.user import User

class History(Base):
    __tablename__ = "history"
    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="user_news_unique"),
        Index("fk_history_user_idx", "user_id"),
        Index("fk_history_news_idx", "news_id"),
        {"comment": "浏览历史表"}
        )
    

    id = Column(Integer, primary_key=True, autoincrement=True, comment="浏览历史ID")
    user_id = Column(
        Integer, 
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, 
        comment="用户ID")
    news_id = Column(
        Integer, 
        ForeignKey("news.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, 
        comment="新闻ID")
    view_time = Column(TIMESTAMP, nullable=False, comment="浏览时间戳")
     
    user = relationship(User)
    news = relationship(News)
