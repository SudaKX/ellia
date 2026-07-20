# Mythos 后端设计 V1

## 1. 目标与原则

`mythos` 是 Ellia 解谜活动的后端，采用单体 FastAPI 应用。后端将业务抽象为对玩家持久化数据的受控操作：框架负责运行时、认证、数据模型、事务、固定 HTTP 端点与模块注册；谜题模块负责活动内容与规则。

核心原则：

- 前端不持有权威的进度、权限、答案或结局状态。
- 后端模块不能直接读写数据库、提交事务或注册 HTTP 路由。
- 模块只能通过框架提供的玩家服务修改玩家数据。
- 模块通过全局服务注册文件、演出、统计项和端点回调。
- 所有可影响剧情的写入在单一数据库事务中完成。
- 初期使用显式硬编码导入模块，不使用动态模块发现。

## 2. 应用结构

```text
mythos/
  pyproject.toml
  src/mythos/
    main.py
    core/                 # 配置、日志、异常、数据库、事务、安全
    auth/                 # 平台玩家注册、登录、JWT、Refresh Cookie
    persistence/          # SQLAlchemy 模型与仓储
    players/              # 玩家数据服务
    global_services/      # 文件、演出、统计等全局注册服务
    endpoints/            # 固定端点、回调派发器、请求响应模型
    registry/             # 模块契约、注册器、启动校验、总目录
    puzzle_modules/       # 所有谜题模块，显式导入
    assets/               # 后端私有静态资源
  migrations/
  tests/
```

技术基线：Python 3.13、FastAPI、SQLAlchemy 2、Alembic、Pydantic Settings、SQLite、Argon2id、pytest。包管理与虚拟环境工具在实现阶段确定，不作为本设计的约束。

## 3. 框架与模块边界

### 3.1 框架职责

框架拥有并实现：

- 配置、日志、异常处理、数据库连接和迁移。
- 平台玩家注册、登录、JWT 验证与刷新凭据管理。
- 玩家持久化数据模型、事务边界、并发版本检查和审计。
- 固定 HTTP 端点、多回调与唯一回调的派发。
- 模块加载、注册目录构建和启动期一致性校验。
- 虚拟文件、演出、统计项等全局资源目录。

### 3.2 模块职责

谜题模块是谜题相关内容的唯一来源。模块可声明：

- 谜题元数据、验证器和完成效果。
- 虚拟文件、目录、内容提供者、访问条件和访问事件。
- ElLInA 演出脚本、触发条件和选项效果。
- checkpoint 和统计项。
- 固定端点上的回调。

模块不得：

- 直接操作 ORM、数据库会话或事务。
- 自行注册 FastAPI 路由。
- 直接调用其他模块的内部实现。
- 向前端下发可执行 JavaScript 或 Vue 组件代码。

跨模块关系只可通过稳定 ID、进度授权项或显式模块依赖表达。

## 4. 玩家数据与服务

### 4.1 数据模型

框架定义并拥有以下持久化实体：

| 实体 | 职责 |
| --- | --- |
| `Player` | 平台玩家身份、创建与最后访问时间。 |
| `PlayerAuth` | 用户名/邮箱、密码哈希、Refresh Selector、Refresh Secret 哈希与过期时间。 |
| `PlayerProgress` | 当前 FakeOS 账户、剧情节点、checkpoint、不可逆状态和权限。 |
| `PlayerModuleState` | 以 `module_id` 隔离、带版本号的模块私有数据。 |
| `PuzzleAttempt` | 答案提交与验证历史。 |
| `PuzzleCompletion` | 谜题完成状态与完成时间。 |
| `PlayerArtifact` | 玩家专属缓存文件、二维码和动态凭据等产物。 |
| `FileAccessLog` | 文件读取、下载和关键访问事件。 |
| `PerformanceState` | 演出触发、进行、完成和选项状态。 |
| `PlayerStatisticEvent` | 玩家侧原始统计事件。 |
| `Ending` | Key、最终操作、结局与结算时间。 |

核心剧情状态使用明确字段。仅谜题私有且结构易变的数据存入 `PlayerModuleState`，并携带模块数据版本。

平台玩家账户与 FakeOS 账户是两套概念：平台账户用于注册、登录和恢复进度；`PLAYER` 与 `JDKTrigger` 是剧情内账户，其可登录性、凭据与权限由玩家进度控制。

### 4.2 玩家服务

模块只能通过以下受限服务读写玩家数据：

- `ProgressService`：读取前置条件、推进剧情、发放授权、管理 checkpoint 和不可逆状态。
- `ValidationService`：记录尝试、调用模块验证器、标记谜题完成。
- `PlayerStatisticsService`：记录玩家维度的统计事件。
- `ArtifactService`：按玩家生成一次并持久化动态文件、密码或二维码。
- `AuditService`：记录文件访问、演出选择和关键操作。

模块返回结构化 `PlayerEffect`，由玩家服务统一执行。典型效果包括：

```text
complete_puzzle(cache-credentials)
grant_account(JDKTrigger)
grant_key(HAPPY_KEY)
unlock_file(sandbox-executable)
set_flag(lock_repaired)
trigger_performance(ellina-warning)
record_statistic(first-ctf-complete)
```

一次唯一回调调用创建一个数据库事务。框架在回调成功后统一提交，发生异常则完整回滚。多回调端点为只读，不允许写入玩家数据。

## 5. 全局服务

全局服务保存模块注册的资源目录，并依据当前玩家上下文提供受限访问：

- `FileService`：注册虚拟目录、文件、访问条件和内容提供者；提供文件树、在线读取、下载与访问审计。
- `PerformanceService`：注册演出脚本、触发条件和选项；提供待演出查询与脚本读取。
- `GlobalStatisticsService`：注册统计项，从 `PlayerStatisticEvent` 聚合活动管理侧数据。
- `EndpointRegistry`：保存端点回调并负责派发。

玩家身份解析与 JWT 验证属于框架核心。文件和演出虽然由全局目录提供，但每次读取仍必须携带玩家上下文，并重新校验账户、进度和访问条件。

动态文件不可在请求时重新随机生成。模块通过 `ArtifactService` 首次生成后持久化产物，后续读取始终返回同一版本内容。

## 6. 模块注册

模块在启动时以显式导入列表加载：

```python
REGISTERED_MODULES = (
    player_intro,
    cache_credentials,
    first_ctf,
    sandbox_route,
)
```

框架依次调用模块的 `register(registrar)`，构建只读注册目录。注册器提供类似以下 API：

```text
register_puzzle(...)
register_virtual_file(...)
register_performance(...)
register_checkpoint(...)
register_statistic(...)
register_multi_callback(...)
register_unique_callback(...)
```

启动期必须拒绝：

- 重复的模块 ID、资源 ID、回调 ID 和虚拟路径。
- 悬挂的谜题、演出、checkpoint 或统计项引用。
- 循环的模块依赖或无效的前置条件。
- 同优先级且声明会覆盖相同响应空间的多回调。

所有模块、资源、演出和动态生成器应有稳定 `revision`。玩家已生成的动态产物和已完成状态不得因模块发布更新而改变。

## 7. 端点与回调

框架预先定义固定端点。模块只能注册回调，不能新增 HTTP 路由。每个回调都必须提供全局唯一、不可重命名的 `stable_id`，例如 `cache-credentials.submit`。

### 7.1 多回调端点

多回调端点用于聚合式只读查询，例如桌面 bootstrap、应用可见性和待演出摘要。

- 请求不携带回调 ID。
- 框架按优先级从小到大调用全部适用回调。
- 回调可读取玩家状态并决定是否贡献数据，但不得写入数据。
- 回调只返回自身的 JSON 对象。
- 框架以回调 `stable_id` 为键聚合响应。

```json
{
  "data": {
    "core.desktop": {
      "account": "PLAYER",
      "privilege": "LIMITED"
    },
    "cache-credentials.desktop": {
      "available": true
    }
  }
}
```

任一必需回调异常时，默认整次请求失败。可选回调必须显式声明，并在响应元数据中报告失败，不能静默省略。

### 7.2 唯一回调端点

唯一回调端点允许注册多个回调，但前端必须在请求中提供 `stable_id`，框架只调用匹配的一项。它适用于谜题答案提交、演出选项、Sandbox 操作等会修改玩家状态的请求。

命令型端点的 `stable_id` 放入请求体，并与业务数据分离：

```json
{
  "stable_id": "cache-credentials.submit",
  "payload": {
    "answer": "..."
  }
}
```

框架在调用回调前验证 JWT、请求格式、`stable_id` 存在性和事务边界。回调负责谜题答案、剧情前置条件、文件可见性和结局资格的业务验证。

资源读取和文件下载等 GET 端点不使用请求体，改用路径或查询参数中的资源 `stable_id`。下载端点直接返回文件流，不采用 JSON 响应聚合。

优先级仅用于多回调端点的调用及展示顺序，不能作为剧情正确性或模块依赖机制。

## 8. 认证与授权

平台采用传统注册/登录，并使用短期 JWT 加长期 Refresh Secret Cookie：

```text
POST /auth/register -> 创建平台玩家与初始进度
POST /auth/login    -> 校验密码，设置 Refresh Cookie，返回短期 JWT
POST /auth/refresh  -> 校验并轮换 Refresh Secret，返回新 JWT
POST /auth/logout   -> 使 Refresh Secret 失效并清除 Cookie
```

密码使用 Argon2id 哈希。Refresh Cookie 的值为：

```text
<refresh_selector>.<high_entropy_secret>
```

`refresh_selector` 是公开、唯一且可索引的定位符；服务端据此查找 `PlayerAuth`，再使用高熵 Secret 的哈希完成验证。Cookie 应使用 `HttpOnly`、`Secure`、`SameSite=Strict` 属性。Refresh Secret 每次刷新时轮换，数据库仅保存其哈希。

JWT 由前端保存在内存中，并在全部业务请求中通过 `Authorization: Bearer <jwt>` 发送。JWT 只包含玩家 ID、认证标识、签发时间和过期时间，不包含进度、权限或 FakeOS 账户信息。

JWT 不做即时吊销：登出会使 Refresh Secret 失效，但已签发 JWT 可用至自然过期。因此 Access Token 应保持短期有效。注册、登录和刷新是无需 JWT 的例外；其他业务端点必须验证 JWT。刷新端点需要额外校验 `Origin` 或 `Referer`，并仅在 HTTPS 部署环境下启用 Secure Cookie。

## 9. 前端 API 边界

建议前端以以下能力与后端通信：

- 认证：注册、登录、刷新和登出。
- 桌面：多回调 bootstrap，获取当前 FakeOS 账户、权限、可见应用和待演出摘要。
- 文件：读取虚拟目录、读取文件元数据、在线内容和原始下载。
- 命令：通过唯一回调端点提交答案、演出选项、checkpoint 操作和 Sandbox 操作。
- 管理侧：读取聚合统计，使用独立管理员鉴权。

前端只维护本地交互状态和 API 响应投影。谜题 ID 到 Vue 组件的映射固定在 Vue 项目中，后端不传输可执行前端代码。

## 10. 首个端到端切片

第一个实现阶段应验证完整边界，而非铺开全部谜题：

```text
平台注册/登录
-> JWT 刷新
-> PLAYER 登录 FakeOS
-> 多回调桌面状态
-> 虚拟文件读取
-> 唯一回调提交一道谜题
-> 原子写入进度、统计与文件解锁
-> 前端重新获取桌面状态
```

在该切片稳定后，依次实现动态哈希缓存谜题、JDKTrigger、ElLInA 演出、锁定分支、Sandbox 结局、管理统计和端到端分支测试。
