from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., max_length=50, description="用户名")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    gender: Optional[Literal["male", "female", "unknown"]] = Field("unknown", description="性别：male/female/unknown")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")

class UserCreate(UserBase):
    password: str = Field(..., max_length=255, description="密码（明文入参，仅用于服务端哈希后存储）")

class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")

class UserUpdate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = Field(None, max_length=255)
    gender: Optional[Literal["male", "female", "unknown"]] = Field(None)
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, max_length=255)
    # 管理后台可更新角色，实现权限分配
    role: Optional[str] = Field(None, description="用户角色：user/reviewer/admin")
    # 管理后台可禁用/启用用户
    status: Optional[str] = Field(None, description="账号状态：active/disabled")


class UserAdminUpdate(BaseModel):
    nickname: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = Field(None, max_length=255)
    gender: Optional[Literal["male", "female", "unknown"]] = Field(None)
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, max_length=255)
    # 管理员通用更新也使用枚举约束，避免非法 role/status 直接打到数据库。
    role: Optional[Literal["user", "reviewer", "admin"]] = Field(None, description="用户角色：user/reviewer/admin")
    status: Optional[Literal["active", "disabled"]] = Field(None, description="账号状态：active/disabled")

class UserOut(UserBase):
    id: int
    # 输出角色与状态，方便前端控制管理权限与展示状态
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class LoginTokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserAdminRoleUpdate(BaseModel):
    role: Literal["user", "reviewer", "admin"] = Field(..., description="目标角色")


class UserAdminStatusUpdate(BaseModel):
    status: Literal["active", "disabled"] = Field(..., description="目标账号状态")


class UserAdminCreate(UserCreate):
    # 管理员创建用户时可指定角色；默认普通用户
    role: Literal["user", "reviewer", "admin"] = Field("user", description="用户角色")
    # 管理员创建用户时可指定状态；默认启用
    status: Literal["active", "disabled"] = Field("active", description="账号状态")

