from sqlalchemy import Column, Integer, String, Enum, TIMESTAMP, text
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
    # 后台权限控制核心字段：区分普通用户/审核员/管理员
    role = Column(Enum('user', 'reviewer', 'admin'), nullable=False, server_default='user', comment="用户角色")
    # 账号状态字段：可用于后台禁用用户而非直接删库
    status = Column(Enum('active', 'disabled'), nullable=False, server_default='active', comment="账号状态")
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        comment="更新时间",
    )