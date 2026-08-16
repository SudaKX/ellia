## Purpose

管理谜题编辑项目（module）的元数据，为实体、WS 房间与文件引用提供归属容器。

## ADDED Requirements

### Requirement: 项目创建

系统 SHALL 提供 `POST /api/projects`，接收 `{module_id, display_name}` 创建项目；请求体中的 `description` 与 `deploy_baseline` 为可选字段。`module_id` MUST 通过共享包 `isValidModuleId` 校验，且 MUST 在全部项目中唯一（不区分大小写比较遵循数据库排序规则）。成功时 SHALL 返回 `201` 与完整项目对象。

#### Scenario: 成功创建

- **WHEN** 已登录用户提交 `{module_id: "example2", display_name: "示例模块"}` 且 `module_id` 未被占用
- **THEN** 系统返回 `201`，响应包含 `id`、`module_id`、`display_name`、`description`、`deploy_baseline`、`created_by`、`created_at`、`updated_at`，其中 `description` 与 `deploy_baseline` 缺省为 `null`

#### Scenario: module_id 重复

- **WHEN** 已登录用户提交已被占用的 `module_id`
- **THEN** 系统返回 `409`，错误码为 `RESOURCE_CONFLICT`

#### Scenario: module_id 非法

- **WHEN** 已登录用户提交含路径分隔符、`.`、`..` 或空字符串的 `module_id`
- **THEN** 系统返回 `400`，错误码为 `VALIDATION`

### Requirement: 项目列表与详情

系统 SHALL 提供 `GET /api/projects` 返回全部项目，按 `updated_at` 降序排列；SHALL 提供 `GET /api/projects/:id` 返回单个项目，不存在时返回 `404 PROJECT_NOT_FOUND`。

#### Scenario: 列表包含全部项目

- **WHEN** 已登录用户请求项目列表
- **THEN** 系统返回 `200`，响应为 `{projects: [...]}`，每个元素包含完整项目字段，顺序按 `updated_at` 降序

#### Scenario: 项目不存在

- **WHEN** 已登录用户请求不存在的项目 id
- **THEN** 系统返回 `404`，错误码为 `PROJECT_NOT_FOUND`

### Requirement: 项目更新

系统 SHALL 提供 `PATCH /api/projects/:id`，允许更新 `display_name`、`description`、`deploy_baseline`；请求包含 `module_id` 时 SHALL 返回 `400 VALIDATION`（module_id 创建后不可修改）。更新成功后 SHALL 刷新 `updated_at` 并返回完整项目对象。

#### Scenario: 更新展示字段

- **WHEN** 已登录用户提交 `{display_name: "新名字", deploy_baseline: "..."}`
- **THEN** 系统返回 `200`，项目 `display_name` 与 `deploy_baseline` 更新，`updated_at` 晚于更新前

#### Scenario: 尝试修改 module_id

- **WHEN** 已登录用户提交包含 `module_id` 的更新请求
- **THEN** 系统返回 `400`，错误码为 `VALIDATION`，原 `module_id` 保持不变

### Requirement: 项目接口认证

项目 CRUD 全部端点 MUST 要求已登录会话；未登录访问 SHALL 返回 `401 UNAUTHORIZED`。所有登录用户（user 与 admin）对任意项目拥有同等读写能力（全局两层权限，无项目级隔离）。

#### Scenario: 未登录被拒绝

- **WHEN** 未携带有效会话 cookie 的请求访问任一项目端点
- **THEN** 系统返回 `401`，错误码为 `UNAUTHORIZED`
