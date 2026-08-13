# Question Review

## Purpose

管理员对 `pending` 题目执行审核：通过（approve）或驳回（reject，附备注）。
审核通过是题目进入"已发布"的唯一路径。

## Requirements

### Requirement: 仅管理员可审核

#### Scenario: 管理员通过

- Given 已登录 `admin` 用户，题目 Q 状态为 `pending`
- When 调用 `POST /api/v1/questions/{Q}/review`（body: `{ approved: true }`）
- Then 状态变为 `approved`，写入 `publishedAt`

#### Scenario: 管理员驳回

- Given 已登录 `admin` 用户，题目 Q 状态为 `pending`
- When 调用 review（body: `{ approved: false, note: "题面缺少密文" }`）
- Then 状态变为 `rejected`，`reviewNote` 记录原因

#### Scenario: 出题者尝试审核

- Given 已登录 `author` 用户
- When 调用 review
- Then 返回 `403 Forbidden`

### Requirement: 仅 pending 状态可审核

#### Scenario: 审核非待审题目

- Given 题目 Q 状态为 `draft`
- When 管理员调用 review
- Then 返回 `409 Conflict`（仅 `pending` 可审核）

### Requirement: 审核不改变题目内容

#### Scenario: 审核通过保留内容

- Given 管理员通过题目 Q
- Then Q 的 title/blocks/options/fillAnswers/hints 与审核前一致

### Requirement: 审核结果对作者可见

#### Scenario: 作者查看驳回原因

- Given 题目 Q 被驳回且 `reviewNote` 存在
- When 作者调用 `GET /api/v1/questions/{Q}`
- Then 返回记录包含 `reviewNote`
