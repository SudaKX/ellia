# Desktop × Mythos 前后端对接

本文档说明 `desktop/`（前端）与 `mythos/`（后端）之间需要对接的位置、对接方式与约束。后端契约以 `mythos/docs/api/` 为准，前端现状以 `desktop/src/` 为准。

## 现状概览

- `mythos/` 是 FastAPI 后端，全部业务路由挂在 `/api/v1` 前缀下（`GET /health` 除外）。
- `desktop/` 目前所有数据均为 mock / 本地实现，唯一总开关是 [api.ts](../src/config/api.ts)：`API_BASE` 与 `USE_REAL_API`。
- 前端现有 mock 与后端契约存在**不一致点**（详见下方各模块），对接时应一并修正，而非照抄现有 `api.ts`。

## 对接点清单

### 1. 鉴权（优先级最高，所有其他接口的前置）

| 项 | 位置 | 现状 | 需对接的后端端点 |
| --- | --- | --- | --- |
| API 配置 | [config/api.ts](../src/config/api.ts) | 端点写死为 `/api/auth/*`，且 `API_BASE=''` | `/api/v1/auth/*` |
| 登录 | [views/LoginView.vue](../src/views/LoginView.vue#L90-L139) | mock：`btoa(username:timestamp)` 当 token | `POST /api/v1/auth/login` |
| 会话恢复 | [composables/useAuth.ts](../src/composables/useAuth.ts#L124-L151) | mock：本地 token 存在即视为有效 | `POST /api/v1/auth/refresh` |
| 登出 | [composables/useAuth.ts](../src/composables/useAuth.ts#L99-L107) | 仅清 localStorage | `POST /api/v1/auth/logout`（需 Bearer） |

**对接方式**

1. `api.ts` 端点修正为 `/api/v1/auth/{login,refresh,logout}`。
2. 现有 `AUTH_ENDPOINTS.validate`（`/api/auth/validate`）与 `tokenLogin`（`/api/auth/token-login`）**后端不存在**：后端无 token 校验端点，会话恢复应改为调 `/refresh`（后端校验 refresh cookie 后签发新 access token）；“密钥登录”应改为用现有 token 调业务接口 + `/refresh` 验证，或移除。
3. access token 保存在**内存**（`useAuth` 单例），不写 localStorage；登录后所有请求带 `Authorization: Bearer <access_token>`。
4. refresh cookie 由后端 `Set-Cookie`（HttpOnly、SameSite Strict、路径 `/api/v1/auth`），前端不读写、不持久化；浏览器在**同源或经代理**场景下自动携带。
5. 401 恢复流程：收到 `401` → 尝试一次 `/refresh` → 成功则重放原请求；失败则清空会话回登录页。

**约束**

- `login` 返回 `{access_token, token_type, expires_in}`（`expires_in` 默认 900s）；注册重复用户名为 `409`，密码错误为 `401`。
- 所有认证响应 `Cache-Control: no-store`。

### 2. 玩家档案

| 项 | 位置 | 现状 | 说明 |
| --- | --- | --- | --- |
| 档案数据 | [stores/archive.ts](../src/stores/archive.ts#L120-L140) | mock 数据 + `fetch('/api/player/archive')` 占位 | **后端不存在该端点** |
| 档案视图 | [components/applications/ArchiveViewer.vue](../src/components/applications/ArchiveViewer.vue) | 消费 `archiveStore` | 已隔离在 store 层，替换 store 即可 |

后端当前没有“玩家档案”聚合端点。对接时二选一：

- 由前端用 `GET /api/v1/progress`（`unlocked_nodes` 等）组装“已完成内容”，其余字段（注册时间、登录次数、成就、游玩时长）需要后端新增端点或扩展 progress 投影。
- 或先新增后端端点再对接；不要沿用 `/api/player/archive` 路径，应使用 `/api/v1/` 前缀。

### 3. 文件系统

| 项 | 位置 | 现状 | 需对接的后端端点 |
| --- | --- | --- | --- |
| 文件树/内容 | [composables/useFileSystem.ts](../src/composables/useFileSystem.ts) | 前端静态树 `rootTree`，`accessRule` 纯函数 | `GET /api/v1/files/ls|tree`、`/files/s/*`、`/files/d/*`、`/files/{file_id}` |
| 文件内容 | [commands/ls.ts](../src/commands/ls.ts)、[commands/cat.ts](../src/commands/cat.ts) | 从 `rootTree` 读 | 目录树 + `GET /files/{file_id}/{content_token}/content-url` 预签名 URL |
| 资源管理器 | [components/applications/FileExplorer.vue](../src/components/applications/FileExplorer.vue) | 消费 `useFileSystem` | 同文件树接口 |

**对接方式**

1. 目录/树响应均含 `path`、`directories`、`files`、`tree_version`；文件摘要含 `file_id`、`path`、`revision`、`media_type`、`size_bytes`、`content_token`、`display`。
2. **读文件内容两步走**：先用 Bearer 调 `GET /files/{file_id}/{content_token}/content-url` 拿到 `{url, expires_at, content_token}`，再直接 `fetch(url)` 对象存储；预签名 URL **不持久化**。
3. 静态树（`/files/*`）只含启动期冻结文件；**动态树（`/files/d/*`）**才合并玩家 Artifact（如 `/archive/recovery-report.txt`），面向玩家的浏览应使用动态接口。
4. 版本协商：`/files/version`、`/files/d/version` 支持 `If-None-Match`，命中返回 `304`；客户端可带上次 `tree_version` 做增量刷新。

**错误处理**（前端动作）

| 状态 | 含义 | 前端动作 |
| --- | --- | --- |
| `403` | 已知文件但无权限 | 从视图中移除该项 |
| `404` | 文件未知 / 目录不可见 | 移除对应本地缓存 |
| `412` | content token 过期 | 刷新 tree/version 后**仅重试一次** |
| `502` / `503` | 对象存储未配置/URL 签发失败 | 保留目录状态，显示“暂不可用” |

### 4. 谜题验证（核心玩法闭环）

| 项 | 位置 | 现状 | 需对接的后端端点 |
| --- | --- | --- | --- |
| 谜题状态 | [composables/usePuzzle.ts](../src/composables/usePuzzle.ts) | localStorage 本地判定 | 改为服务端验证 + 进度 |
| 谜题注册 | [registries/puzzles.ts](../src/registries/puzzles.ts)、[components/puzzles/](../src/components/puzzles/) | 前端静态注册 | 由 `GET /api/v1/scripts` 驱动 |
| 答案提交 | [components/puzzles/ExampleCipher.vue](../src/components/puzzles/ExampleCipher.vue) | `usePuzzle.submitAnswer` 本地比对 | `POST /api/v1/validations/{validation_id}/attempts` |

**对接方式**

1. `GET /api/v1/scripts` 返回当前玩家可见脚本 `{items: [{stable_id, revision, body}]}`；`body` 含 `schema_version` 与 `kind`（当前有 `answer-validator`、`notice`）。前端按 `kind`/`schema_version` 分派渲染，不假设未知 kind 的字段。
2. 提交验证：`POST /api/v1/validations/{validation_id}/attempts`，payload 为模块定义 JSON（Example 为 `{"answer":" ECHO-7 "}`），必须带 `Request-ID: <UUID>`。
3. `accepted: false` 是正常业务拒绝，仍返回 `200`，前端保留当前页面状态。
4. **提交成功后必须重新请求** `GET /api/v1/progress`、`GET /api/v1/scripts`、动态文件树（`/files/d/version` 或 `/files/d/tree`）——服务端可能同时推进进度、生成 checkpoint、产出 Artifact。

**Request-ID 幂等规则**（命令类接口通用，含 checkpoint restore）

- 一次用户意图生成一个 UUID；网络错误重试用**相同 ID**；新意图用新 ID。
- `409`（同 ID 执行中，含 `Retry-After: 1`）→ 短暂等待后用原 ID 重试。
- 幂等缓存仅当前进程 TTL 内有效（默认 30s），不能当永久去重。

### 5. 进度与 checkpoint

前端目前没有进度 UI。接入项：

| 后端端点 | 用途 | 备注 |
| --- | --- | --- |
| `GET /api/v1/progress` | 读 `unlocked_nodes`、`frontier_nodes`、`version` | 返回 `current_account` 等；`version` 变化时应刷新受进度保护的文件/脚本 |
| `POST /api/v1/progress/checkpoints/restore` | 恢复存档 | 命令类，需 `Request-ID`；无 checkpoint 为 `404`，不兼容为 `409` |

## 通用对接约定

### API 基地址与开关

- 统一在 [config/api.ts](../src/config/api.ts) 维护：`API_BASE`（后端地址）与 `USE_REAL_API`（mock/真实切换），端点集中在 `*_ENDPOINTS` 常量。
- 生产环境 `base: '/console/'`（见 [vite.config.ts](../vite.config.ts)）；后端如与前端同域部署，`API_BASE` 可设为 `/api`。

### 认证与 401 恢复

所有业务接口（除 `register`、`login`、`refresh`、`/health`）要求 `Authorization: Bearer <access token>`。统一在请求封装层（建议新建 composable 或复用 `useAuth`）注入 header 并处理 401 恢复。

### 错误码映射（跨端点通用）

| 状态 | 含义 | 前端动作 |
| --- | --- | --- |
| `401` | token 缺失/失效 | 尝试一次 `/refresh`；失败则清空会话 |
| `403` | 已知但无权限 | 移除对应本地状态 |
| `404` | 未知资源/不可见目录/无 checkpoint/未知 validation | 移除本地状态，不区分存在性 |
| `409` | Request-ID 冲突 / 进度冲突 / checkpoint 不兼容 | 刷新状态；仅执行中请求可用原 ID 重试 |
| `412` | content token 过期 | 刷新 tree/version 后重试一次 |
| `502` / `503` | 对象存储 URL 签发失败/未配置 | 保留目录，提示暂不可用 |

### 缓存与敏感信息

- 目录、metadata、认证响应、download URL 均为 `no-store`；content URL 可私有缓存，其 max-age < 签名 TTL。
- **禁止持久化**：access token、refresh cookie、预签名 URL。

### 开发期跨域

后端当前未配置 CORS（`mythos/src/mythos/main.py` 无 `CORSMiddleware`），且 refresh cookie 为 SameSite Strict。开发联调建议在 [vite.config.ts](../vite.config.ts) 加 dev server 代理（`/api` → 后端地址），避免浏览器直连后端产生的跨域与 cookie 问题。

## 对接顺序建议

1. 鉴权（`api.ts` 端点修正 → `useAuth` 内存 token → LoginView 真登录 → 401 恢复）。
2. 文件系统（动态树浏览 → 预签名 URL 读文件 → 错误映射）。
3. 谜题验证（scripts 驱动 → validation 提交 → 成功后进度/脚本/动态树刷新）。
4. 进度与 checkpoint（档案组装 → restore）。

## 相关后端文档

- 契约索引：[`mythos/docs/api/README.md`](../../mythos/docs/api/README.md)
- 认证 / 命令 / 文件 / 进度 / 脚本 / 验证 / 错误：`mythos/docs/api/{authentication,commands,files,progress,scripts,validations,errors-and-caching}.md`
- 调用流程示例：`mythos/docs/api/example-flow.md`
