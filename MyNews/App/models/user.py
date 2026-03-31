from sqlalchemy import Column, Integer, String, Enum, TIMESTAMP, func
from models.news import Base

class User(Base):
    __tablename__ = "user"
    __table_args__ = {
        "comment": "用户信息表"
    }

    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    password = Column(String(255), nullable=False, comment="密码（加密存储）")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    gender = Column(Enum('male', 'female', 'unknown'), default='unknown', nullable=True, comment="性别")
    bio = Column(String(500), nullable=True, comment="个人简介")
    phone = Column(String(20), unique=True, nullable=True, comment="手机号")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间")