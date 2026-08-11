# Question Publishing

## Purpose

把审核通过的题目以公开只读接口暴露给游戏端（desktop），实现"审核后自动发现"。
接口无需登录，响应与前端 PuzzleDefinition 契约一致。

## Requirements

### Requirement: 已发布题目公开可读

#### Scenario: 匿名拉取已发布题库

- Given 数据库中存在 `status = approved` 的题目
- When 调用 `GET /api/v1/questions/published`
- Then 返回 `{ version, questions: PuzzleDefinition[] }`，仅含已发布题

#### Scenario: 未发布题目不出现

- Given 存在 `draft/pending/rejected` 状态的题目
- When 拉取 published
- Then 响应中不包含这些题目

### Requirement: 发布响应剔除管理字段

#### Scenario: 响应不含作者与审核信息

- When 拉取 published
- Then 每条题目不含 `authorUsername`、`reviewNote`、`status`、`createdAt/updatedAt/publishedAt`

### Requirement: 发布响应含答案（本地校验契约）

#### Scenario: 单选题答案随题下发

- Given 已发布单选题
- Then `questions[].options[].correct` 存在（desktop 本地校验与现有游戏模式一致）

#### Scenario: 填空答案随题下发

- Given 已发布填空题
- Then `questions[].fillAnswers` 存在

### Requirement: 发布结果稳定可缓存

#### Scenario: 发布列表带版本与缓存头

- When 拉取 published
- Then 返回 `version` 字段，响应头允许 `Cache-Control` 缓存（审核变更后失效）
