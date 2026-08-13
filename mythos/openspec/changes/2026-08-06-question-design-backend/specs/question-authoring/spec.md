# Question Authoring

## Purpose

题目的创建/读取/编辑/删除与生命周期状态机：
`draft → pending → approved | rejected`；编辑已发布题自动回到 `pending`。

## Requirements

### Requirement: 题目以 PuzzleDefinition 契约存储

#### Scenario: 创建单选/多选/填空题目

- Given 出题者提供 `{ title, blocks, type, options|fillAnswers, hints, explanation }`
- When 调用 `POST /api/v1/questions`
- Then 创建 `status = draft` 的题目并返回完整记录

#### Scenario: 选项数量越界

- Given 选择题选项数量 < 2 或 > 10
- When 提交创建
- Then 返回 `422 Unprocessable Entity`（Pydantic 校验）

### Requirement: 出题者仅能操作自己的题目

#### Scenario: 列出本人题目

- Given 已登录 author 用户 A
- When 调用 `GET /api/v1/questions/mine`
- Then 仅返回 A 创建的题目

#### Scenario: 编辑他人题目被拒

- Given author 用户 A 与题目 Q（作者为 B）
- When A 调用 `PUT /api/v1/questions/{Q}`
- Then 返回 `403 Forbidden`

### Requirement: 题目生命周期状态机

#### Scenario: 草稿提交审核

- Given 题目状态为 `draft`
- When 调用 `POST /api/v1/questions/{id}/submit`
- Then 状态变为 `pending`

#### Scenario: 已发布题被编辑后重新进入审核

- Given 题目状态为 `approved`
- When 作者调用 `PUT /api/v1/questions/{id}` 修改内容
- Then 状态重置为 `pending`，`publishedAt` 清空，需重新审核

#### Scenario: 已发布题不可重复提交

- Given 题目状态为 `approved`
- When 调用 `POST /api/v1/questions/{id}/submit`
- Then 返回 `409 Conflict`

### Requirement: 删除规则

#### Scenario: 作者删除自己的题目

- Given 已登录 author 用户 A，题目 Q 作者为 A
- When 调用 `DELETE /api/v1/questions/{Q}`
- Then 删除成功

#### Scenario: 作者删除他人题目被拒

- Given 题目 Q 作者为 B
- When 用户 A 调用 `DELETE /api/v1/questions/{Q}`
- Then 返回 `403 Forbidden`

### Requirement: 幂等与请求重放保护

#### Scenario: 同 Request-ID 重放

- Given 已用 Request-ID R 提交过一次写请求
- When 以相同 Request-ID R 重放
- Then 返回缓存结果而非重复执行（复用 mythos RequestCache）
