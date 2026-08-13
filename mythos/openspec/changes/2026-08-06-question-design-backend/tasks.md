# Question Design Backend — 任务拆分

按依赖顺序执行，每步完成后可独立验证。

## T1. 复制 mythos → question-server

- 目录级复制 `mythos/` → `question-server/`（含 src、migrations、tests、pyproject、alembic.ini、openspec、docs）。
- 包名保持 `mythos`，避免大规模改名；`question-server/README.md` 注明"出题器后端独立副本"。
- 验证：副本内 `pytest` 全量通过；`uvicorn` 可启动，`/health` 返回 ok。

## T2. 角色扩展（author | admin）

- 迁移 `0012_question_roles.py`：`PlayerRecord` 增加 `role` 列（默认 `author`）。
- `src/mythos/questions/seed_admin.py`：CLI 从 `ADMIN_USERNAME/ADMIN_PASSWORD` 创建首个 `admin`（幂等）。
- `auth/dependencies.py` 增加 `require_admin` 依赖。
- 测试：`test_question_roles.py`（注册默认 author；seed_admin 幂等）。

## T3. 题目持久化模型

- `persistence/models/questions.py`：`Question`（id UUID、title、blocks JSON、type、options JSON、
  fill_answers JSON、hints JSON、explanation、status、review_note、author_id FK、created/updated/published_at）。
- 迁移 `0013_questions.py`。
- 测试：迁移后表结构可用。

## T4. 题目 registry（definitions/catalog/registry）

- 遵循现有 `registry/*` 模式（dataclass definitions + catalog + registry），
  注册进 `RegistryBundle`；题目内容为玩家数据（运行时创建），registry 仅承载 schema/校验规则，
  不承载具体题目实例。
- 说明：与 hints/tasks 不同，questions 是"用户生成内容"，实际存储走 DB（T3），
  registry 层提供类型/校验/序列化的集中定义。

## T5. 题目服务（CRUD + 权限 + 状态机）

- `services/questions/service.py`：create/get/list_mine/list_all/update/delete/submit/review/test。
- 权限：author 本人；admin 全部+任意删除+审核。
- 状态机：draft→pending（submit）；pending→approved|rejected（review）；approved 编辑→pending。
- 测试：`test_question_authoring.py`（CRUD/越权/状态机）。

## T6. 题目端点（endpoints/questions.py）

- 挂载进 `endpoints/router.py`（`/api/v1/questions`）：
  - `POST /` 创建草稿（author）
  - `GET /mine`（author）；`GET /all`（admin）
  - `GET /{id}`（本人或 admin）
  - `PUT /{id}`（本人；approved 编辑→pending）
  - `DELETE /{id}`（本人；admin 任意）
  - `POST /{id}/submit`（本人）
  - `POST /{id}/review`（admin）
  - `POST /{id}/test`（本人，答案校验不落库）
  - `GET /published`（公开只读）
- 复用 `EndpointCommandExecutor` 事务管线 + RequestCache（幂等/重放保护）。
- 测试：`test_question_endpoints.py`（含权限矩阵、published 过滤、RFC 9457 错误格式）。

## T7. 文档

- `docs/api/questions.md`：端点契约表 + 请求/响应示例 + 权限说明。
- 更新 `docs/README.md` 端点索引。

## T8. 端到端验证

- 起服务：注册 author → 建题 → 提交审核 → admin 审核通过 → `GET /published` 可见且不含未审核题。
- desktop 联调（可选，开关 `USE_PUBLISHED_QUESTIONS`）：
  - desktop_designer 的 `useQuestionApi.ts` 切换为真实 fetch（仅改此文件）；
  - desktop 拉取 published 自动发现新题。
