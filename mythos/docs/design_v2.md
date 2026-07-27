# Mythos 后端设计 V2

本文取代 V1 中与玩家访问、Action、Effect、Service 和注册器有关的约定。认证、异步 SQLite、JWT、Refresh Cookie 和 Request-ID 短时去重保持不变。

## 1. 分层

- `persistence/` 保存 SQLAlchemy 记录模型。`PlayerRecord` 是数据库记录，不向业务模块暴露。
- `players/` 提供请求级 `Player` 聚合对象及其数据库访问 Interface。
- `services/` 保存应用级全局 Service。Service 接收请求级 Player 和冻结后的 Catalog，不保存请求、Session 或玩家状态。
- `registry/` 按动态内容类型维护注册期对象，并冻结为运行期 Catalog。
- `core/commands/` 提供命令事务、RequestCache 和可缓存响应模型。
- `core/followups.py` 提供跨 Service 的客户端 followup 协议。

## 2. Registry 与 Runtime

`RegistryBundle` 组合 validations、files、progress 和 scripts 四类注册期对象。模块在应用启动前显式调用 `register(registries)`；静态文件 Source 在 `freeze()` 前由启动期发布器物化为 RustFS `ObjectReference`，随后 `RegistryBundle.freeze()` 结束注册期并生成 `RuntimeCatalogs`。运行期消费者按约定只读使用 Catalog。

```text
RegistryBundle -> RuntimeCatalogs -> ApplicationRuntime
```

`ApplicationRuntime` 保存运行期 Catalog、PlayerFactory、全局 Service 和 `CommandTransactionExecutor`，并通过 `app.state.runtime` 提供给 Router。Service 使用具体 `Player` 调用模块注册的纯 Read 权限函数；Registry 不创建或保存 Player。

`RuntimeCatalogs.progress` 保存启动期冻结的 `ProgressGraph`。模块以可读字符串 ID 注册 ProgressNode，Graph 生成稳定数字 ID 供玩家状态持久化使用。ProgressInterface 管理 unlocked/frontier 节点集合、分支和自动 merge；checkpoint 约定见 [Progress V1](progress_v1.md)。

## 3. Player 与 Interface

`PlayerFactory` 在应用启动时绑定 `RuntimeCatalogs`，并在每个请求中以 `AsyncSession` 和 JWT 身份创建一个 `Player`。创建 Player 时，Factory 将同一份 Catalog 引用注入每个 Interface。`Player` 组合多个 Interface；V2 初始仅实现 `ProgressInterface`。

```text
Player
└── progress: ProgressInterface
```

`RequestContext` 包含身份、只读或可写 Player 与私有 followup 收集器。`CommandContext` 在此基础上携带非空 `Request-ID`，仅由 `CommandTransactionExecutor` 在事务内创建。Service 与 Interface 都可读取 `RuntimeCatalogs`；Interface 不取得 Service、Session 或 `ApplicationRuntime`。只读 Player 不能修改 Interface 状态；可写 Player 的 Interface 直接修改受当前 Session 追踪的 ORM 记录，模块不能取得 Session 或自行提交事务。进度推进统一使用 `player.progress.push(id, branch_arg)`。

## 4. 命令事务

命令型模块 handler 先通过 Player 读取前置条件，直接调用可写 Interface 修改状态，并返回由具体 Registry 定义的领域 Outcome。Service 将 Outcome 映射为 `ResponseSpec`，因此框架不要求通用的模块 handler 返回类型。

`CommandTransactionExecutor` 在语义化命令 handler 的外层开启数据库事务，负责 Request-ID reserve、可写 Context、提交、回滚和缓存。Service 的 `ResponseSpec.body` 是领域 content；Executor 在事务内执行 pre-commit hook、冻结 Context followups，组装 `{ "content": ..., "followups": ... }` 后才提交和缓存最终响应。进度 checkpoint hook 在此阶段原子写入本地快照并登记 metadata。任一异常、拒绝、非法响应或非法 followup 都会回滚事务并释放 Request-ID 占位。

V2 暂不提供统一的乐观锁或并发版本保护。具体 Interface 或 Service 在出现真实并发约束时定义条件更新、SQLAlchemy versioning、唯一约束或其他保护机制。版本字段是否返回给客户端由具体 Service 决定，Executor 不注入全局状态版本。

## 5. Service

每个 Service 是启动期创建一次的全局对象，并拥有自己的 FastAPI Router：

```text
services/files/    # FileService 与文件 API
services/progress/ # ProgressService、checkpoint 与进度 API
services/scripts/  # ScriptService 与演出脚本 API
services/validations/ # ValidationService 与验证提交 API
```

Service 通过请求级 Player 判断内容可见性。GET Router 通过 `get_read_context()` 使用 `writable=False` 的 `RequestContext`；写入 Router 通过 `CommandTransactionExecutor` 创建 `writable=True` 的 `CommandContext`，并复用命令事务与 Request-ID，不能直接提交 Session。

FileService 的静态文件注册分为 `register_source(FileReference)` 与 `register_node(VirtualNode)`。Source 使用 `module + relative_path` 定位 `puzzles/<module>/` 下的本地文件；启动期发布器以 mtime 物化或复用 RustFS 对象，FileTree 仅保存已解析的 `ObjectReference`。FileTree 提供仅反映静态 Catalog 的 `tree_version`，每个文件提供由 Node revision 与对象 VersionId 派生的 `content_token`；两者均不包含玩家进度。公开文件 ID 和预签名下载 URL 约定见 [FileService V1](file_service_v1.md)。

## 6. Registry

- `registry/files/`：虚拟 Node、静态文件 Source、路径、revision 和访问规则。
- `registry/progress/`：ProgressNode 注册与冻结后的进度 DAG。
- `registry/scripts/`：演出脚本、revision 和访问规则。
- `registry/validations/`：验证尝试 ID 与模块注册的验证 handler。

语义化 Service 提供固定 HTTP 端点，例如 `POST /api/v1/validations/{validation_id}/attempts`。模块只能向对应 Registry 注册 handler，不能暴露泛型 callback endpoint 或新增 HTTP 路由。所有 Registry 在应用启动时冻结；V2 当前允许显式注册列表为空。
