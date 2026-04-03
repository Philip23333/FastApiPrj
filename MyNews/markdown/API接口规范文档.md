# MyNews API 接口规范文档

更新时间：2026-03-26

## 1. 总览

- 后端框架：FastAPI
- 默认地址：`http://127.0.0.1:8080`
- 路由前缀：无全局 `/api` 前缀
- 文档地址：`/docs`（Swagger）

## 2. 认证与鉴权

### 2.1 认证方式

- 使用 JWT Bearer Token。
- 登录后从返回体 `data.access_token` 取 token。
- 受保护接口请求头格式：

```http
Authorization: Bearer <access_token>
```

### 2.2 角色权限

- `user`：普通用户。
- `reviewer`：审核员，可访问新闻审核后台接口。
- `admin`：管理员，可访问用户管理和新闻审核后台接口。

### 2.3 账号状态

- `active`：可登录、可访问受保护接口。
- `disabled`：禁止登录，访问受保护接口会返回 403。

## 3. 通用响应结构

所有业务接口统一返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

分页数据结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 100,
    "page": 1,
    "size": 10,
    "totalPages": 10,
    "items": []
  }
}
```

说明：

- `code` 为业务码，成功通常是 `200` 或 `201`。
- HTTP 状态码仍然有效，错误时优先结合 HTTP 状态码判断。

## 4. 用户模块 `/users`

### 4.1 登录（业务登录）

- `POST /users/login`
- 鉴权：否
- 请求体：

```json
{
  "username": "alice",
  "password": "123456"
}
```

- 返回：`access_token`、`token_type`、`expires_in`、`user`

### 4.2 OAuth2 标准 token 端点

- `POST /users/token`
- 鉴权：否
- 说明：Swagger Authorize 使用该接口。
- Content-Type：`application/x-www-form-urlencoded`
- 参数：`username`、`password`

### 4.3 注册

- `POST /users/register`
- 鉴权：否
- 请求体字段：
  - 必填：`username`、`password`
  - 可选：`nickname`、`avatar`、`gender`（`male/female/unknown`）、`bio`、`phone`

### 4.4 用户详情

- `GET /users/{user_id}`
- 鉴权：否
- 说明：按 id 查询用户公开信息。

### 4.5 用户更新（本人）

- `PUT /users/{user_id}`
- 鉴权：是（当前登录用户）
- 规则：
  - 仅允许本人更新自己的信息。
  - 普通更新接口禁止改 `role/status`。
  - `phone` 需唯一。

### 4.6 管理员用户列表

- `GET /users/admin?skip=0&limit=100`
- 鉴权：`admin`

### 4.7 管理员查看用户详情

- `GET /users/admin/{user_id}`
- 鉴权：`admin`

### 4.8 管理员更新用户（通用）

- `PUT /users/admin/{user_id}`
- 鉴权：`admin`
- 可更新字段：`nickname/avatar/gender/bio/phone/password/role/status`
- 枚举约束：
  - `gender`: `male/female/unknown`
  - `role`: `user/reviewer/admin`
  - `status`: `active/disabled`

### 4.9 管理员单独改角色

- `PATCH /users/admin/{user_id}/role`
- 鉴权：`admin`
- 请求体：

```json
{
  "role": "reviewer"
}
```

### 4.10 管理员单独改状态

- `PATCH /users/admin/{user_id}/status`
- 鉴权：`admin`
- 请求体：

```json
{
  "status": "disabled"
}
```

### 4.11 管理员删除用户

- `DELETE /users/admin/{user_id}`
- 鉴权：`admin`

## 5. 新闻模块 `/news`

### 5.1 新闻搜索建议

- `GET /news/search/suggest?q=关键词&limit=5`
- 鉴权：否

### 5.2 新闻搜索

- `GET /news/search?q=关键词&page=1&size=10`
- 鉴权：否
- 规则：仅返回 `approved` 且未删除新闻。

### 5.3 新闻列表（首页）

- `GET /news/?page=1&size=10`
- 鉴权：否
- 规则：仅返回 `approved` 且未删除新闻。

### 5.4 热榜

- `GET /news/hot?min_views=5000&page=1&size=8`
- 鉴权：否

### 5.5 新闻详情

- `GET /news/detail/{news_id}`
- 鉴权：是（登录用户）
- 规则：
  - `rejected` 或已删除新闻返回 404（新闻已下架）。
  - 访问详情会增加浏览量。

### 5.6 分类列表

- `GET /news/categories?skip=0&limit=100`
- 鉴权：否

### 5.7 分类新闻列表

- `GET /news/categories/{category_id}/news?page=1&size=10`
- 鉴权：否
- 规则：仅返回 `approved` 且未删除新闻。

### 5.8 发布新闻

- `POST /news/`
- 鉴权：是（登录用户）
- 请求体核心字段：

```json
{
  "title": "标题",
  "content": "正文",
  "category_id": 1,
  "category_name": "科技",
  "image": "/static/uploads/xxx.jpg",
  "description": "摘要"
}
```

- 规则：
  - `category_id` 与 `category_name` 必须匹配。
  - 新发布默认进入审核流（通常为 `pending`）。

### 5.9 作者更新新闻（重提审核）

- `PUT /news/{news_id}`
- 鉴权：是（作者本人）
- 规则：
  - 仅作者可改。
  - 修改后会重置审核状态为 `pending`，用于重新提交审核。

### 5.10 作者删除新闻

- `DELETE /news/{news_id}`
- 鉴权：是（作者本人）

### 5.11 我的作品

- `GET /news/mine?page=1&size=20`
- 鉴权：是
- 说明：返回当前用户作品列表（含审核状态、驳回原因、审核时间）。

### 5.12 作者可编辑详情

- `GET /news/editable/{news_id}`
- 鉴权：是（作者本人）
- 说明：用于发布页编辑回填，拒稿内容也可回填再编辑。

### 5.13 审核后台新闻列表

- `GET /news/admin/list?page=1&size=20&audit_status=pending`
- 鉴权：`reviewer` 或 `admin`
- `audit_status` 可选值：`pending/approved/rejected/draft`

### 5.14 审核操作（通过/拒绝/改分类）

- `PATCH /news/admin/{news_id}/moderation`
- 鉴权：`reviewer` 或 `admin`
- 请求体（可部分传）：

```json
{
  "category_id": 2,
  "audit_status": "rejected",
  "audit_remark": "标题党，内容不符合规范"
}
```

- 规则：
  - 至少传一个更新字段。
  - `audit_status = rejected` 时 `audit_remark` 必填。
  - `audit_status = approved` 时会清空驳回原因。

## 6. 收藏模块 `/favorites`

### 6.1 收藏列表

- `GET /favorites?page=1&size=10`
- 鉴权：是

### 6.2 收藏新闻

- `POST /favorites/{news_id}`
- 鉴权：是

### 6.3 取消收藏

- `DELETE /favorites/{news_id}`
- 鉴权：是

### 6.4 查询是否已收藏

- `GET /favorites/check/{news_id}`
- 鉴权：是
- 返回：`data` 为 `true/false`

## 7. 历史记录模块 `/history`

### 7.1 历史记录列表

- `GET /history?page=1&size=10`
- 鉴权：是
- 说明：
  - 若新闻已下架（删除或 rejected），该条会返回 `is_removed = true`。
  - 下架条目仍保留历史记录，但详情不可访问。

### 7.2 添加历史记录

- `POST /history/{news_id}`
- 鉴权：是
- 规则：下架新闻不可新增历史记录。

### 7.3 删除历史记录

- `DELETE /history/{news_id}`
- 鉴权：是

## 8. 文件上传模块 `/files`

### 8.1 上传图片

- `POST /files/upload`
- 鉴权：当前代码未强制鉴权（建议前端仍在登录态使用）
- 请求类型：`multipart/form-data`
- 字段：`file`
- 限制：仅允许 `image/*`
- 返回示例：

```json
{
  "code": 200,
  "message": "图片上传成功",
  "data": {
    "url": "/static/uploads/8f4e....jpg"
  }
}
```

## 9. 关键业务规则（联调必读）

1. 首页、分类页、搜索页只展示审核通过（`approved`）的新闻。
2. 被拒稿（`rejected`）或已删除新闻在详情接口视为下架，返回 404。
3. 作者修改新闻后自动回到 `pending`，必须重新审核通过才会再次出现在前台列表。
4. 历史记录支持下架态回显（`is_removed=true`），前端应展示“新闻已下架”并禁用跳转。
5. 后台审核接口允许 `reviewer/admin`，用户管理接口仅 `admin`。

## 10. 常见错误码

- 400：参数错误、业务校验失败（如分类不匹配、手机号重复）。
- 401：未登录或 token 无效。
- 403：已登录但无权限或账号被禁用。
- 404：资源不存在或资源已下架。
- 422：请求体格式/字段校验失败（Pydantic 校验错误）。
- 500：服务端异常（应通过日志定位）。