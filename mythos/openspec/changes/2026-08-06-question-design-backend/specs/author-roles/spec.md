# Author Roles

## Purpose

出题者账号体系：注册/登录（复用 mythos JWT 认证）与 `author|admin` 角色判定。
普通出题者仅能操作自己的题目，管理员可操作全部题目并执行审核。

## Requirements

### Requirement: 账号注册即成为出题者

#### Scenario: 新用户注册

- Given 一个尚未注册的用户名
- When 调用 `POST /api/v1/auth/register`
- Then 创建 `role = author` 的账号并返回 access_token

#### Scenario: 用户名重复

- Given 用户名已被注册
- When 再次调用注册
- Then 返回 `409 Conflict`

### Requirement: 首个管理员由种子流程创建

#### Scenario: 空库创建管理员

- Given question-server 数据库为空
- When 执行 `python -m mythos.questions.seed_admin`（从环境变量 ADMIN_USERNAME/ADMIN_PASSWORD）
- Then 创建 `role = admin` 的账号

#### Scenario: 管理员已存在时重复执行

- Given 已存在 admin 账号
- When 再次执行 seed_admin
- Then 不报错且不覆盖既有管理员

### Requirement: 角色由数据库列决定，端点校验

#### Scenario: author 访问他人题目

- Given 已登录的 `author` 用户 A
- When 请求编辑作者 B 的题目
- Then 返回 `403 Forbidden`

#### Scenario: admin 访问任意题目

- Given 已登录的 `admin` 用户
- When 请求任意作者的题目
- Then 允许读取/编辑/删除

### Requirement: 认证令牌沿用 mythos JWT 机制

#### Scenario: 携带有效 token 调用受保护端点

- Given 已登录用户持有 access_token
- When 请求 questions 受保护端点
- Then 通过 `get_current_player` 识别出作者身份

#### Scenario: 无 token 调用受保护端点

- When 匿名请求 questions 受保护端点
- Then 返回 `401 Unauthorized`
