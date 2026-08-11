# Question Design Backend — 变更提案（Analysis）

> 本提案使用 OpenSpec（spec-driven）工作流编写，目标：建立"谜题出题后端"，
> 为出题者提供账号/题目管理/审核/发布能力，供游戏端（desktop）自动发现。

## Why

游戏端（desktop）目前只有纯前端的出题器（desktop_designer，localStorage 模拟），
存在三个硬伤：

1. **数据隔离于浏览器**：题库存在本地 localStorage，换设备/换浏览器即丢失，多人协作不可能。
2. **答案可见性无法保证**：发布 JSON 含答案明文，任何打开控制台的人都能看到正确答案。
3. **无服务端校验**：游戏端本地校验答案，无法作为"正式结算"依据。

游戏后端 mythos 已具备成熟的认证（JWT + refresh cookie）、事务管线、registry
注册体系、Alembic 迁移与 RFC 9457 错误响应——在其副本上扩展 questions 模块，
即可用最小成本获得上述能力，并保持与游戏端现有契约（PuzzleDefinition）一致。

## What Changes

- **复制 mythos → question-server**：独立副本（不动原 mythos），作为出题后端的代码基座。
- **角色扩展**：`PlayerRecord` 增加 `role` 列（`author` | `admin`），提供种子 CLI 创建首个管理员。
- **新增 questions 领域**：持久化模型 + registry（definitions/catalog/registry）+ service + endpoints。
- **题目生命周期**：`draft → pending → approved | rejected`，编辑已发布题自动重置为 `pending`。
- **发布接口**：`GET /api/v1/questions/published` 公开只读（无需登录），返回不含作者/审核备注的完整
  PuzzleDefinition 集合，供 desktop 自动发现。
- **测试接口**：作者可对草稿提交答案做本地校验（服务端不落库）。
- 不修改数据库 schema 之外的结构，不引入新的依赖。

## Capabilities

### New Capabilities

- `author-roles`: 出题者账号注册/登录与 `author|admin` 角色判定。
- `question-authoring`: 题目 CRUD 与生命周期状态机（draft/pending/approved/rejected）。
- `question-review`: 管理员审核（approve/reject + 备注）。
- `question-publishing`: 已发布题目的公开只读接口与自动发现契约。

### Modified Capabilities

无（question-server 是独立副本，不修改原 mythos 的任何能力）。

## Impact

- 新目录 `question-server/`（mythos 的完整副本），原 `mythos/` 零改动。
- 新增文件（均在副本内）：
  - `src/mythos/persistence/models/questions.py` + 迁移 `0012_question_roles.py`、`0013_questions.py`
  - `src/mythos/registry/questions/{definitions,catalog,registry}.py`
  - `src/mythos/services/questions/service.py`
  - `src/mythos/endpoints/questions.py`（挂载进 `endpoints/router.py`）
  - `src/mythos/commands` 无需改动（题目操作是普通写命令，复用 EndpointCommandExecutor 事务管线）
- 测试：`tests/test_question_*.py`；文档：`docs/api/questions.md`。
- 不改动 desktop / desktop_designer（接入由 desktop 的 `USE_PUBLISHED_QUESTIONS` 开关后续联调）。

## 与分析对象的关系

本提案的端点契约（见 specs/）与前端 `desktop_designer` 的 `useQuestionApi.ts`
函数签名一一对应（list/create/update/delete/submit/review/exportPublished），
未来把出题器从 localStorage 切到本后端时只改该文件内部实现。
