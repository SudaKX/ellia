# 回调函数约定汇总

本文汇总 Mythos 当前由系统调用的回调函数合同，说明注册位置、参数、返回值、同步或异步要求，以及调用时的事务边界。

模块只能在启动期向既有 Registry 注册内容和回调。Registry 在应用开始提供服务前冻结，模块不能新增通用 callback HTTP 路由。固定 Router、FastAPI Dependency 和普通 Service 方法不属于模块可注册回调。

## 模块扩展回调

| 回调 | 注册位置 | 合同 | 要求 | 调用边界 |
| --- | --- | --- | --- | --- |
| Validation attempt handler | `ValidationAttempt.handler` | `(CommandContext, Mapping[str, Any]) -> Awaitable[ValidationOutcome]` | 必须异步 | `EndpointCommandExecutor` 的 Operation transaction 内；异常会回滚并释放 Request-ID lease |
| Player lifecycle handler | `LifecycleRegistry.register_lifecycle()`、`on_construct`、`on_deconstruct` | `(PlayerLifecycleContext) -> Awaitable[None]` | 必须异步 | Construct/Deconstruct 分发事务内；按 `EARLY`、`DEFAULT`、`LATE` 和注册顺序调用，首个异常中止后续回调 |
| Artifact generator | `ArtifactTemplate.generator` | `(Player) -> Awaitable[RawArtifact]` | 必须异步、恰好一个位置参数 | 由 Artifact Interface 在命令或重建流程中调用；对象存储写入发生在 SQL 提交前 |
| Artifact node generator | `ArtifactNodeTemplate.node_generator` | `(Player, Mapping[str, Any], ArtifactNode) -> Awaitable[ArtifactNode]` | 必须异步、恰好三个位置参数 | 由 Artifact Interface 调用；meta 来自 Artifact generator |
| 静态文件 access rule | `StaticNodeSpec`、文件 manifest | `(Player) -> bool` | 必须同步、纯读取、恰好一个位置参数、带 callback ID；当前静态文件路由只加载 `PROGRESS | ACCOUNTS` | FileService 在静态目录遍历、文件路径链和下载授权时直接求值 |
| Artifact Node access rule | `ArtifactNodeTemplate.access_rule` | `(Player) -> bool` | 必须同步、纯读取、恰好一个位置参数、带 callback ID 和显式 `PlayerInterfaces` dependency；动态文件路由加载 `PlayerInterfaces.ALL` | FileService 在动态目录遍历、文件路径链和下载授权时直接求值 |
| Hint access rule | `Hint.access_rule` | `(Player) -> bool` | 必须同步、纯读取、恰好一个位置参数 | HintService 在列表、购买与预签名 URL 签发前求值 |
| Script access rule | `Script.access_rule` | `(Player) -> bool` | 必须同步、纯读取；当前脚本路由只加载 `PROGRESS | ACCOUNTS`，不承诺其他 Interface 可用 | ScriptCatalog 在读取脚本列表时直接求值 |
| Progress branch selector | `BranchProgressNode.how` | `(Any) -> tuple[str, ...]` | 必须同步 | ProgressGraph 在推进分支节点时直接求值；返回目标必须是声明过且不重复的字符串 ID |

### 异步回调

Validation、Lifecycle 和 Artifact 回调的调用点均直接使用 `await`。它们可读取或修改当前事务中的 Player 状态；不得自行创建事务、提交 Session，或持有请求结束后的 Session。

Lifecycle Construct 在注册和既有玩家首次真实登录时触发。Lifecycle 回调失败会使 Construct 标记与同一事务中的状态修改一并回滚。

Artifact generator 与 node generator 必须以 `module_handler(module)(revision)` 标记。静态文件和 Artifact Node access_rule 必须使用 `module_handler(module)(revision, dependencies=...)` 显式声明依赖；静态文件当前只支持由静态路由预加载的 `PROGRESS | ACCOUNTS`，Artifact Node 的动态路由使用 `PlayerInterfaces.ALL`。未声明依赖的文件规则在注册或 freeze 阶段拒绝。callback ID 使用 schema 2 和新的固定 UUID namespace，依赖 mask 的变化会触发对应资源版本变化。

`node_generator` 返回的 path 必须保持 `ArtifactNodeTemplate.path`，不能修改节点身份路径；display、hidden 和 download name 仍可按既有规则生成运行时值。

当前 `HintInterface` 没有可用于文件版本计划的状态 revision，因此 Hint disclosure 不能声明为文件 access_rule 依赖。未来若开放该依赖，必须先增加独立的 Hint state revision 和对应迁移，再加入 `VersionedPlayerInterface` 版本向量。

### 同步决策回调

access rule 与 branch selector 必须是快速、确定、无副作用的普通函数。它们只应读取已经加载的 Player 状态，不得执行数据库、对象存储、网络或阻塞 I/O。

不能将 `async def` 用作同步决策回调。调用同步 access rule 时，协程对象在 Python 中为真值，可能将未执行的异步权限规则错误地视为允许访问；branch selector 则会因返回值不符合 `tuple[str, ...]` 而失败。不要用 `asyncio.run()`、线程跳转或事件循环嵌套来适配这类回调。

## 框架组合回调

下列回调由应用组合代码注册或调用，不是模块扩展点，仍须遵守所属框架的合同。

| 回调 | 注册或定义位置 | 要求 |
| --- | --- | --- |
| Puzzle module 注册函数 | `puzzles.register_all()` 直接调用各模块 `register(registries)` | 必须同步；仅在启动期物化 Registry 内容 |
| Command pre-commit hook | `PipelinedTransaction(pre_commit_hooks=...)` 或 TaskService 配置 | 必须异步，合同为 `(AsyncSession, Player) -> Awaitable[None]`；在事务提交前按配置顺序执行，异常回滚当前 transaction |
| FastAPI lifespan | `FastAPI(lifespan=...)` | 必须为异步 context manager；负责静态文件物化、Catalog 冻结、reconciliation 和数据库释放 |
| FastAPI exception handler | `application.add_exception_handler()` | Starlette 兼容同步或异步 handler；当前 Mythos 实现使用异步函数 |
| SQLAlchemy SQLite connect listener | `event.listen(..., "connect", ...)` | 必须同步 DBAPI 回调；用于连接建立期设置 SQLite PRAGMA |
| Pydantic model validator | `@field_validator`、`@model_validator` | 必须遵循 Pydantic 同步校验合同；用于输入和配置对象的规范化、校验 |

## 兼容性原则

当前模块 callback 类型按调用语义区分为异步命令/生成回调与同步查询/决策回调，而不是统一为单一 `async def` 类型。

若未来需要提供兼容适配，应只允许将简单的同步函数适配到异步回调位置。不能反向将异步函数适配到同步位置：系统已经运行在事件循环中，并且 Player 与 `AsyncSession` 不可透明地跨线程或跨事件循环使用。适配器还必须保留 Artifact callback 的 `__callback_id__`，避免无意改变模板版本。
