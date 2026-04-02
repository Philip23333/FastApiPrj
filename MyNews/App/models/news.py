from datetime import datetime
from email.mime import image
from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, desc, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase,Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )

class Category(Base):
    __tablename__ = "news_category"

    id: Mapped[int] = mapped_column(Integer,primary_key=True, autoincrement=True,comment="分类ID")
    name: Mapped[str] = mapped_column(String(50),unique=True, nullable=False, comment="分类名称")
    sort_order : Mapped[int] = mapped_column(Integer, default=0,nullable=False, comment="排序字段，数值越小越靠前")

    # 建立与News表的一对多反向关系（可选，方便查询该分类下的所有新闻）
    news: Mapped[list["News"]] = relationship("News", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', sort_order={self.sort_order})>"

class News(Base):
    __tablename__ = "news"

    # 创建索引
    __table_args__ = (
        Index("idx_news_category_id", "category_id"), # 分类ID索引，优化按分类查询
        Index("idx_news_publish_time", "publish_time"), # 发布时间索引，优化按时间排序查询
    )


    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="新闻ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻标题")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="新闻简介")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="新闻内容")
    image: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="封面图片URL")
    author: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="作者")
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_category.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="分类ID")
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="浏览量")
    publish_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="发布时间")
    # 审核状态：后台可基于该字段做待审/通过/驳回列表
    audit_status: Mapped[str] = mapped_column(
        Enum('draft', 'pending', 'approved', 'rejected', name='news_audit_status_enum'),
        default='pending',
        nullable=False,
        comment="审核状态"
    )
    # 审核备注：记录驳回原因或审核说明
    audit_remark: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="审核备注")
    # 审核人ID：预留给后台管理员审核追踪
    audited_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="审核人用户ID"
    )
    # 审核时间：记录审核动作发生时间
    audited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="审核时间")
    # 软删除标记：后台删除可先软删，保留审计与恢复能力
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否软删除")
    
    # 定义与Category表的关系，方便级联查询
    category: Mapped["Category"] = relationship("Category", back_populates="news")

    def __repr__(self) -> str:
        return f"<News(id={self.id}, title='{self.title}', category_id={self.category_id}, views={self.views})>"
