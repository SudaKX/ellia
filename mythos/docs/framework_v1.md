# Mythos 后端框架 V1

本文记录 V1 的框架基线。Player Interface、Service、Registry 与 Effect 语义已由 [设计 V2](design_v2.md) 取代；认证、异步数据库和短期请求去重约定仍适用。

## 1. 框架边界

Mythos 是单体 FastAPI 应用。框架拥有认证、数据库、事务、玩家状态模型、固定端点和模块注册目录；模块提供谜题规则、文件、演出、checkpoint、统计项和端点回调。

模块不得直接操作 ORM、`AsyncSession`、事务或 FastAPI 路由。模块只能使用框架提供的查询上下文、`Action` 和 `PendingEffect` 具体类型。

框架目录约定：

```text
src/mythos/
  auth/          # 平台账户、JWT、Refresh Cookie
  core/          # Settings、异步数据库和通用安全能力
  persistence/   # SQLAlchemy Base、模型和迁移支持
  players/       # 玩家查询、Effect 构建和状态执行服务
  resources/     # 文件、演出、统计等全局资源目录
  endpoints/     # 回调端点与 Action 派发
  registry/      # 模块契约、注册与启动校验
  puzzles/       # 显式导入的谜题模块
```

## 2. 异步运行时与数据库

V1 使用 Python `asyncio`、FastAPI、SQLAlchemy Async 和 `aiosqlite`。所有请求处理、数据库会话和模块回调使用异步接口；Argon2id 密码哈希通过 `asyncio.to_thread()` 执行，避免阻塞事件循环。

SQLite 是唯一权威数据源。数据库连接启用：

- `PRAGMA foreign_keys=ON`
- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`

所有玩家写操作由一个 `AsyncSession` 事务包裹。V1 部署使用单个应用 worker；SQLite 不作为多 worker 或多实例的横向扩展数据库。

Alembic 管理迁移，应用启动时不自动迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic -c mythos/alembic.ini upgrade head
```

当前基础模型：

| 模型 | 责任 |
| --- | --- |
| `Player` | 平台玩家 ID、显示用户名、规范化用户名和访问时间。 |
| `PlayerAuth` | Argon2id 密码哈希和单组 Refresh 凭据。 |
| `PlayerProgress` | 当前 FakeOS 账户、剧情节点、checkpoint 与状态版本。 |

后续谜题完成、动态产物、文件访问、演出、统计和结局模型继续由框架拥有，但由对应服务和 Effect 统一写入。

## 3. 平台认证

平台玩家账户与 FakeOS 中的 `PLAYER`、`JDKTrigger` 是两套概念。前者用于平台登录和恢复存档，后者属于玩家剧情状态。

认证端点为框架核心端点，不进入模块回调派发：

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

认证采用短期 Access JWT 和长期 Refresh Cookie：

- Access JWT 有效期默认 15 分钟，通过 `Authorization: Bearer <token>` 携带。
- JWT 仅包含 `sub`、`iss`、`aud`、时间声明、`jti` 和类型；不包含进度、权限或 FakeOS 账户。
- Refresh Cookie 值为 `<selector>.<secret>`，使用 `HttpOnly`、`SameSite=Strict`，生产环境启用 `Secure`。
- 数据库只保存 Refresh Secret 的 HMAC-SHA256 值和 selector，不保存明文。
- 登录和刷新会轮换 Refresh Cookie；V1 每位玩家只保留一组刷新凭据。
- 登出清除刷新凭据。已签发 JWT 不做即时吊销，在自然过期前仍有效。

生产环境必须由环境变量提供至少 32 字节的 JWT 签名密钥和 Refresh Pepper。开发环境缺失密钥时生成进程内临时密钥，仅适合本地开发。

## 4. 玩家请求上下文

框架不将 JWT 直接当作完整玩家状态。受保护请求首先通过 JWT 依赖获得最小身份：

```text
PlayerIdentity
- player_id
```

唯一回调端点再从数据库构造：

```text
PlayerRequestContext
- identity: PlayerIdentity
- snapshot: PlayerSnapshot
- player_queries: PlayerQueryService
- request_id: UUID
```

`PlayerSnapshot` 包含前端和模块判断所需的玩家状态投影，例如当前剧情节点、FakeOS 账户、checkpoint、授权项和状态版本。模块不接触 ORM 实体、原始数据库会话或 Effect 执行器；状态变更只能通过 `EffectAction` 执行。

多回调端点只使用只读上下文。框架一次加载快照后传给所有回调，避免重复查询。

## 5. 端点与模块回调

框架预定义 HTTP 端点，模块只能向已有端点注册回调。所有回调使用全局唯一、不可重命名的 `stable_id`。

V1 曾使用以下通用端点；它们已在 V2 中移除，改由语义化 Service 端点替代：

```text
GET  /api/v1/views/{endpoint_id}
POST /api/v1/commands/{endpoint_id}
```

### 多回调端点

- 请求不携带 `stable_id`。
- 框架按回调注册优先级调用。
- 回调只能返回 `ResponseAction` 和 `FollowupAction`。
- 各回调响应按其 `stable_id` 聚合。
- 不允许修改玩家数据或返回 `EffectAction`。

### 唯一回调端点

- 可注册多个回调。
- 请求体携带 `stable_id`，框架仅调用匹配回调。
- 写端点必须携带 `Request-ID: <UUID>`。
- 回调返回 `tuple[Action, ...]`。
- 框架在一个玩家事务内顺序执行该元组。

文件读取、下载等资源端点使用资源 stable ID 查询或路径参数。若读取会推进剧情，推荐使用单独的“打开文件”命令端点，而非在可重试的下载 GET 请求中产生状态变更。

## 6. Action

`Action` 是框架定义的抽象执行单元。Action 执行逻辑由自身 `execute(runtime)` 指定，但所有具体实现均由框架提供，模块不得新增 Action 子类。

```text
Action
├── EffectAction
├── ResponseAction
├── FollowupAction
└── RejectAction
```

`ActionRuntime` 包含：

```text
PlayerRequestContext
事务所属 AsyncSession
ResponseBodyBuilder
服务注册目录
```

Action 不直接发送 HTTP 响应。`ResponseAction` 和 `FollowupAction` 只向内存中的 `ResponseBodyBuilder` 写入数据；数据库提交成功后，框架才将其转换为 HTTP 响应。

`RejectAction` 是终止 Action。执行后立即中断并回滚事务，后续 Action 不执行。若需要记录错误答案或失败尝试，应使用 `RecordAttemptEffect` 加 `ResponseAction` 返回业务失败结果，而不是 `RejectAction`。

框架不再排序 Action。唯一回调端点严格按模块返回元组的声明顺序执行；多回调端点按回调优先级收集，再保持每个元组内部顺序。

## 7. PendingEffect 与计划

`PendingEffect` 是尚未执行的原子玩家状态变更。它不是数据库操作结果，也不支持 `+=` 或 `-=`。

框架当前只实现 `SetCheckpointEffect`，用于验证完整的 Action、事务和缓存链路。其余 Effect 会与实际领域模型、迁移和测试一起按需实现。

框架提供的 Effect 包括但不限于：

```text
CompletePuzzleEffect
GrantAccountEffect
GrantKeyEffect
GrantFileEffect
SetCheckpointEffect
SetFlagEffect
CreateArtifactEffect
TriggerPerformanceEffect
RecordStatisticEffect
SetEndingEffect
RestoreCheckpointEffect
```

`PendingEffectPlan` 用于收集 Effect，并提供链式 API：

```python
plan = (
    PendingEffectPlan()
    .add(CompletePuzzleEffect(...))
    .add(GrantAccountEffect(...))
    .extend([CreateArtifactEffect(...), TriggerPerformanceEffect(...)])
)
```

Plan 不提供公开冻结接口。`EffectAction(plan)` 构造时隐式冻结 Plan，记录不可变的 Effect 序列；冻结后的 Plan 不能再调用 `add()`、`extend()` 或其他修改方法。

框架不重新排序 PendingEffect。`EffectAction.execute()` 按 Plan 中的声明顺序逐个调用 Effect 的框架执行逻辑。模块负责保证因果顺序，例如：完成谜题、发放账户、创建动态凭据、触发演出、记录统计。

## 8. 事务与回退

唯一回调端点的执行过程：

```text
验证 JWT 与 Request-ID
-> RequestCache 预约请求
-> 加载 PlayerRequestContext
-> 调用模块回调，得到 Action 元组
-> async with session.begin()
   -> 按声明顺序执行 Action
   -> EffectAction 按计划顺序执行 PendingEffect
-> 数据库提交
-> 冻结 ActionExecutionResult
-> 写入 RequestCache
-> 生成 HTTP 响应
```

任一 Action 或 Effect 失败时，数据库事务回滚此前所有未提交写入。事务回滚不是通过删除或反向执行 PendingEffect 实现。

已提交剧情的 checkpoint 回退属于新的 `RestoreCheckpointEffect`。它依照 checkpoint 规则恢复允许恢复的逻辑状态，并保留不可逆标记、审计信息和结局记录。

数据库事务不能回退邮件、WebSocket、第三方 HTTP、Redis 或真实文件系统等外部副作用。这些操作未来应通过提交后的 Outbox 或 AfterCommit 机制执行。当前动态谜题产物优先存入数据库，以保持状态原子性。

## 9. RequestCache

`RequestCache` 仅用于短时重复写请求复用。V1 使用进程内 `cachetools.TTLCache`，缓存键只有 `Request-ID`。

缓存状态：

```text
不存在                    请求尚未处理
None                      请求正在执行
ActionExecutionResult     请求已完成，可重放纯数据结果
```

`ActionExecutionResult` 是纯数据对象：

```text
owner_player_id   内部安全校验，不向前端序列化
status_code
body
headers
followups
state_revision
```

缓存不存储 `FastAPI Response`、ORM 实体、会话、JWT、Refresh Secret 或 Cookie 明文。

本地缓存的 `reserve()` 在一次无 `await` 的同步代码段内完成检查与写入：

```python
entry = cache.get(request_id, MISSING)
if entry is MISSING:
    cache[request_id] = None
elif entry is None:
    raise RequestInProgressError
else:
    return entry
```

在单一事件循环中，这能避免两个协程在 `get()` 与插入 `None` 之间交错。第二个请求发现 `None` 时返回：

```text
409 Conflict
Retry-After: 1
```

数据库提交成功后，`None` 被替换为 `ActionExecutionResult`。事务异常、请求取消或执行失败时必须删除 `None` 占位，允许前端以同一 Request-ID 重试。

Request-ID 只作为缓存键，因此前端必须为每个逻辑写请求生成全新的 UUID v4，并在网络重试中复用原 ID。缓存命中时必须校验内部 `owner_player_id` 与当前 JWT 玩家一致，避免跨玩家重放。

该缓存仅覆盖单进程、单 worker、未过期且未被容量淘汰的短时重复请求。它不替代数据库唯一约束、状态版本检查和前置条件校验，也不支持多进程或多实例幂等。

## 10. Redis 决策

V1 不引入 Redis：

- SQLite 是玩家状态的唯一权威来源。
- 模块注册目录在进程启动时构建为只读内存数据。
- `RequestCache` 仅为单进程短期去重，不需要分布式缓存。
- JWT 不做即时吊销，不需要黑名单缓存。

未来迁移到 PostgreSQL、多 worker 或多实例后，可将 RequestCache 替换为 Redis 或持久化命令表，并将 Redis 用于分布式限流和管理统计缓存。
