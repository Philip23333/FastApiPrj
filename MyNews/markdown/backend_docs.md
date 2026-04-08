# MyNews 后端项目文档 (FastAPI + SQLAlchemy)

## 1. 项目简介
MyNews 后端是一个基于 Python FastAPI 框架构建的高性能异步 Web API 服务。为前端提供新闻分类、新闻列表流查询、以及支持自增浏览量的新闻详情接口。本系统使用 MySQL 关系型数据库存储数据。

## 2. 技术栈
- **框架**: FastAPI (支持高并发的异步 Web 框架)
- **数据库访问**: SQLAlchemy 2.0 (采用 AsyncSession 异步 ORM)
- **依赖注入**: 使用 FastAPI 的 `Depends` 处理数据库会话等共享逻辑。
- **数据库**: MySQL 8.x

## 3. 核心目录与架构设计
为了保证代码的可维护性，后端采取典型的横向分层结构：

- `models/`: **实体模型层**。
  - 基于 `DeclarativeBase` 定义。通过 `Mapped` 和 `mapped_column`。
  - 主要包含 `Category`(分类表) 和 `News`(新闻表)。利用了 `relationship("Category", back_populates="news")` 等防止级联问题的设置。
- `crud/`: **数据库操作层**。
  - 核心模块，封装了直接交互的所有 `statement` 和操作细节。
  - **核心操作**: `select()`, `session.execute(stmt)`, `scalars().all()`，这是 SQLAlchemy 2.0+ 异步编程的经典三步走设计。
- `routers/`: **路由层 / 控制器**。
  - 注册带有分组和前缀策略 (`prefix="/news"`) 的 `APIRouter`。
  - 接收外部 HTTP 请求，对传入参数(如翻页 `page`, `size`)进行类型校验，随后调用对应的 `crud` 方法获取数据。
- `config/`: **配置层**。
  - 主要存在 `db_config.py`，配置访问引擎，包括如何生成 `get_db()` （基于 `yield` 的异步上下文管理器）。
- `main.py`: **应用入口**。
  - 包含跨域等中间件 (CORS Middleware) 配置，整合包含各类路由，并用于启动应用。

## 4. 关键接口与功能设计

### 4.1 获取新闻列表与分类新闻
- **接口路径**: 
  - `GET /news/?page=1&size=10`
  - `GET /news/categories/{category_id}/news?page=1&size=10`
- **逻辑重难点**:
  - `select(News).options(joinedload(News.category))`：非常重要的一步，这使用了 **连表加载(Eager Loading)**，一次性将外键对应的 Category 数据取出，防止了 N+1 SQL 查询性能灾难。
  - 考虑到前后端分离传递的便利性，在 `routers` 中手动遍历了模型查询列表将其映射转换成标准化的 `dict` 字典并包含了分页必要的 `total` 与 `totalPages` 计算返回给前端。

### 4.2 获取新闻详情与浏览量自增
- **接口路径**: `GET /news/detail/{news_id}`
- **逻辑思路 (重点)**: 
  - 通过 `crud/news.py` 的 `get_news_by_id` 抓取单个 ORM 对应的 News 对象。
  - **逻辑自增**: 如果对象存在，直接在该对象上操作 `news.views += 1`。
  - **事务提交/刷新**: 调用 `await db.commit()` 将缓存存入数据库；紧接着使用 `await db.refresh(news)` 读取最新的数据库状态以保证返回给外部是增加了1之后的确切数据状态。
  - 为了前端“相关推荐”功能，此处还在返回载荷中明确保留了 `category_id` 和文章全正文内容。

## 5. 重点概念复习
- **AsyncSession 与 异步编程**: 引入了 `await db.execute()`。由于 Python 并发编程限制，不能像传统同步直接取数据，必须先获得 `Result` 对象并最终通过 `.scalars()` 解析解包出对象实体。
- **ORM 数据组装与响应**: 直接 `return News模型` 会导致 FastAPI/Pydantic 在序列化外键级联对象时出现无限递归或循环错误。所以最好的工程实践通常是在 Router 里面，将对象剥离出前端实际需要展示和引用的字段字典（例如把原本的模型重新组装为一个 `{"id": news.id, "title": news.title... }` 的纯数据体）。

## 6. 统一响应规范（成功与失败）

后端已统一采用固定响应结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 6.1 成功响应
- 普通成功：HTTP `200`，响应体 `code=200`
- 创建成功：HTTP `201`，响应体 `code=201`
- 分页列表：`data` 统一为 `total/page/size/totalPages/items`

### 6.2 异常响应
- 业务/资源异常（`HTTPException`）：统一转换为 `code/message/data`
  - 例如 404：`code=404`, `message="User not found"`, `data=null`
- 参数校验异常（`RequestValidationError`）：
  - HTTP `422`
  - 响应体：`code=422`, `message="Validation Error"`, `data` 为校验错误列表

### 6.3 实现位置
- 响应工具函数：`App/utils/response.py`
- 全局异常处理：`App/main.py`
- 路由响应模型：`ApiResponse`

### 6.4 迁移收益
- 前端仅需一种解析逻辑（`code/message/data`）
- 网关与日志系统可按 HTTP 状态码和 `code` 同步判断
- 新增字段（如 trace_id）可在响应工具层集中扩展

## 7. Pydantic Schemas 与用户模块 CRUD 相关笔记

### 7.1 解决 ModuleNotFoundError (相对与绝对导入)
- 在同级级联引用时，应避免使用 `from news import Base`。
- **绝对导入**：`from models.news import Base`（推荐）。
- **相对导入**：`from .news import Base`（`.` 表示当前目录）。

### 7.2 Pydantic V1 方法使用及数据映射转换
在 FastAPI 中，借助 Pydantic Schema（数据结构定义）实现前后端交互，并负责“传入字段验证/转化”及“返回字段屏蔽”。

1. **分层 Schema 策略**:
   - `UserBase`: 通用基本字段（ username 等）。
   - `UserCreate`: 增加接受 `password` 等不能直接泄露的核心保密信息。
   - `UserUpdate`: 提供给 PUT 请求，所有参数全部设置为 `Optional` 可以选填。
   - `UserOut`: `Config` 加开启 `orm_mode=True` 支持转换，且故意不声明 `password` 作为返回值的屏蔽（过滤隐私信息）。

2. **`.dict()`**: 把 Schema 对象转 Python 原生字典。
   - **用途**：`db_user = User(**user.dict())` 把前端传入结构转化为 SQLAlchemy 的 Model 实例化传参。

3. **`exclude_unset=True`**: 仅提取被用户明确赋值的内容。
   - **用途**：`user_update.dict(exclude_unset=True)` 用于更新场景。防止像 `nickname=None` 这样默认生成的 `None` 值错误覆盖掉数据库中原本有值的栏位。它能确保“请求发来什么字段就只更新什么字段”。

4. **`from_attributes = True` 与 `.from_orm()`**: 连携使用。处理响应输出机制。
   - **说明点**: SQLAlchemy 查询结果是“Object”而非字典。将内部类 `Config` 配置打开后，`Pydantic` 允许直接去解析 Object 中相应的点 `.` 属性。
   - **用途**：`UserOut.from_orm(db_user).dict()` 直接把后端查出的带有各种脏数据/隐私数据和级联查询的 `db_user` 对象，过滤切片转化为结构干净安全的 API 返回明文字典。
   - *(注：Pydantic V2 会将对应的方法变更为 `model_dump()`, 配置名改为 `model_config={"from_attributes": True}`, 解析方法变为 `model_validate()`)*
