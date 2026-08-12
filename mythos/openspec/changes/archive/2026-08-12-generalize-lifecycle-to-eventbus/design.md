## Context

当前 `registry/lifecycle` 只按 Construct 和 Deconstruct 两种 Player 生命周期事件保存监听器，`services/lifecycle` 的 Dispatcher 仅逐个 await handler。它已具备进程内、同步、有序、调用方事务内执行的属性，但事件类型和命名无法承载虚拟账号登录等普通领域事件。主动成就授予需要在 `POST /vac/login` 的 Operation transaction 内响应 Guest 登录，而不能把 Example 模块规则硬编码进 AccountService 或 HTTP endpoint。

项目已有 RegistryBundle 启动注册与 freeze、RuntimeCatalogs、`module_handler` 依赖声明、PlayerLoader 及 `PipelinedTransaction`。EventBus 必须保持这些边界：模块不拥有 Session 或 transaction；Service 不依赖 HTTP、Request-ID 或 EventBus；事务由 CommandExecutor 或明确 Workflow 所有。

## Goals / Non-Goals

**Goals:**

- 用可扩展的进程内 EventBus 取代专用 LifecycleRegistry 和 PlayerLifecycleDispatcher。
- 支持模块按具体事件类型、优先级和稳定注册顺序注册异步监听器，并在 freeze 时验证回调依赖。
- 在调用方既有 transaction 内同步派发事件；监听器使用已加载 Player 聚合进行写入。
- 迁移 Player Construct/Deconstruct，并提供虚拟账号登录事件供后续模块使用。
- 保持 Auth 不执行 Task，且不让 EventBus 进入 ServiceContainer 或创建 HTTP callback 路由。

**Non-Goals:**

- 不实现消息队列、Outbox、持久化事件、跨进程广播、后台 worker、重试或死信队列。
- 不实现主动成就 `grant`、新的成就定义或 Example 成就展示。
- 不改变现有 HTTP URL、Request-ID 协议、数据库 schema 或已提交 Operation 后的 Achievement C/D 语义。
- 不保留 LifecycleRegistry、`on_construct`、`on_deconstruct` 或 PlayerLifecycleDispatcher 的兼容别名。

## Decisions

### 将 EventBus 设为独立包，注册入口保留在 RegistryBundle

新增 `mythos/eventbus/`，包含事件定义、registry、冻结 catalog、派发 context 和 dispatcher。`RegistryBundle.events` 负责启动期内容注册，`RuntimeCatalogs.events` 持有只读 EventCatalog，`ApplicationRuntime.event_dispatcher` 持有 Dispatcher。

不将其保留在 `services/lifecycle`：事件派发不是领域服务，不能成为 ServiceContainer 的依赖。也不将全部实现折叠进 `core`：它有 Registry/Catalog 的内容模型，独立包能清晰表达其基础设施性质并避免 `core` 继续膨胀。

### 事件为不可变数据，派发上下文包含已加载 Player

定义基类 `Event`，包含 `occurred_at`；玩家相关事件使用 `PlayerEvent`，包含 `player_id`。首批具体类型为：

- `PlayerConstructedEvent(player_id, occurred_at, trigger)`，保留 `registration` 与 `first_login` trigger。
- `PlayerDeconstructingEvent(player_id, occurred_at, trigger="deletion")`，在删除前派发。
- `VirtualAccountLoggedInEvent(player_id, occurred_at, account_id)`。

监听器接收 `EventContext(player, event, scope)`，而不是 Session 或 HTTP request。PlayerEvent 必须携带与 context Player 匹配的 player_id；不关联 Player 的通用 Event 可以使用 `player=None`。Dispatcher 再以精确事件类型查询 listener。这样事件对象可在无 HTTP 的 Workflow 中构造，监听器的 Player Interface 写入仍归属调用方 transaction。

不采用字符串 topic 或继承层级匹配：两者使 listener 覆盖范围隐晦，也难以稳定验证事件 payload。事件类型是显式的 Python 类，派发只匹配注册的实际类型。

### 注册接口沿用 module handler 依赖约束和既有优先级语义

`EventRegistry.on(event_type, *, priority=EventPriority.DEFAULT)` 返回装饰器；它只接受 Event 子类和异步、单参数的 listener。Listener 必须由 `module_handler` 标注依赖，freeze 前或注册时通过现有 callback 校验；Catalog 按 `(priority, registration_sequence)` 返回稳定 listener 顺序。

EventContext 不按 listener dependency 动态加载接口。transaction owner 在派发前以事件所需依赖并集加载 Player：账户登录至少加载 `ACCOUNTS | events.dependencies_for(VirtualAccountLoggedInEvent)`，Auth Construct 则加载 Construct 事件依赖。这个选择避免 Dispatcher 取得 Session/Loader 并暗中扩大聚合或锁范围。

### 调用方显式派发，不使 Domain Service 依赖 EventBus

AccountService 继续只修改 AccountInterface 并返回 snapshot；`/vac/login` endpoint 的 operation 在 `AccountService.login()` 成功后调用 `runtime.event_dispatcher.publish(...)`。AuthService 的 Construct workflow 直接在它拥有的 transaction 内发布 `PlayerConstructedEvent`，替换 lifecycle dispatcher。删除 workflow 在真正删除 Player 数据前派发 `PlayerDeconstructingEvent`。

该方案比向 AccountService 注入 Dispatcher 更符合 transaction-neutral Service 边界；也比由 ORM hook 隐式发布更容易确定发布时序和失败语义。

### 派发失败传播至事务所有者

EventBus 不捕获、转换或重试监听器异常。调用方在自己的 `session.begin()` 和 Pipeline 内 `await publish()`；任一 listener 失败将使当前 Operation 或 Workflow 失败并回滚。现有已提交 Operation 后的 Achievement Check/Effect 仍由 Executor 处理，EventBus 不跨越该边界。

对于 `PlayerDeconstructingEvent`，监听器在玩家仍可加载、仍可写入关联状态时执行。系统不提供 `PlayerDeconstructedEvent`，因为当前无 Outbox，删除提交后无法安全地再使用该玩家聚合。

## Risks / Trade-offs

- [监听器异常使同步业务失败] -> 这是事务内扩展点的明确语义；不适合失败可容忍的外部副作用，后者需要未来独立的 Outbox change。
- [发布方漏掉事件] -> 将首批发布点限制在 Auth Construct、玩家删除和虚拟账号登录，逐一添加单元与集成测试；不引入隐式 ORM hook。
- [监听器依赖未被发布方加载] -> Catalog 提供事件级依赖并集，所有发布点以该并集加载 Player；Dispatcher 同时可在 handler 访问未加载接口时自然失败并回滚。
- [删除旧 API 破坏外部 puzzles] -> 这是明确 breaking change；迁移路径是在同一版本将 `on_construct` / `on_deconstruct` 改写为 `events.on(PlayerConstructedEvent)` / `events.on(PlayerDeconstructingEvent)`。
- [EventBus 被误用为异步消息系统] -> 规格明确禁止持久化、跨进程、重试与后台投递，并以同步 `await` API 保持语义可见。

## Migration Plan

1. 实现 EventBus 包并接入 RegistryBundle、RuntimeCatalogs 和 ApplicationRuntime。
2. 迁移 Auth Construct、玩家删除和所有 puzzles 的 lifecycle 监听器；使用事件 catalog 依赖加载 Player。
3. 在虚拟账号登录 Operation 内发布 `VirtualAccountLoggedInEvent`，不添加模块监听器或成就 grant。
4. 删除 `registry/lifecycle`、`services/lifecycle` 及其 export，更新受影响测试、文档和类型导入。
5. 发布时必须完整运行后端测试；回滚代码时需要一并回滚 puzzle 注册 API 变更，不涉及数据库迁移或持久化数据。

## Open Questions

- 无。后续若需要事件元数据、跨聚合事件或可靠投递，必须在独立 change 中设计，不能扩展本 EventBus 的同步事务内语义。
