# In-Process EventBus

## Purpose

定义进程内同步领域事件的注册、冻结、派发顺序、事务边界、内建事件时机，以及旧生命周期 API 的迁移约束。

## Requirements

### Requirement: Event definitions, listeners and catalogs are registered and frozen

系统 SHALL 提供独立的 EventRegistry。模块 SHALL 在启动期按具体 Event 类型注册异步单参数 listener，并声明 EventPriority。listener SHALL 使用既有 `module_handler` 声明 Player Interface 依赖。Registry SHALL 拒绝非 Event 类型、非异步 listener、错误参数数量、缺少依赖声明、重复 listener 注册和 freeze 后的修改；freeze SHALL 生成只读 EventCatalog。

#### Scenario: Register and freeze a typed event listener

- **WHEN** 模块在 freeze 前为 `VirtualAccountLoggedInEvent` 注册合法 listener
- **THEN** EventCatalog SHALL 提供该事件类型的有序 listener 及其 Player Interface 依赖并集

#### Scenario: Reject an invalid event listener

- **WHEN** 模块注册同步 listener、参数数量错误的 listener，或未声明 module handler 依赖的 listener
- **THEN** EventRegistry SHALL 拒绝注册并报告定义错误

#### Scenario: Reject registry mutation after freeze

- **WHEN** 模块在 EventRegistry freeze 后注册 listener
- **THEN** Registry SHALL 拒绝该修改

### Requirement: Event dispatch is synchronous, ordered and transaction-neutral

系统 SHALL 提供 EventDispatcher，接收调用方构造的 `EventContext`，其中包含可选的已加载 Player、不可变 Event 和既有 ContextScope。PlayerEvent 的 context SHALL 提供与 event.player_id 一致的 Player；不关联 Player 的通用 Event 可以使用 `player=None`。Dispatcher SHALL 仅按事件的精确类型依次 await listener；顺序 SHALL 由较低 EventPriority、随后注册顺序决定。Dispatcher SHALL NOT 创建 Session、加载或锁定 Player、提交或回滚 transaction、构造 HTTP 响应、管理 Request-ID、捕获 listener 异常或执行后台投递。

#### Scenario: Dispatch listeners in deterministic order

- **WHEN** 同一事件类型注册多个不同优先级和注册顺序的 listener
- **THEN** Dispatcher SHALL 按 priority 再按注册顺序 await 每个 listener 一次

#### Scenario: Listener writes join caller transaction

- **WHEN** 调用方在 `session.begin()` 内以 writable Player 派发事件，且 listener 修改 Player Interface
- **THEN** 该修改 SHALL 参与调用方 transaction，调用方提交时一并持久化

#### Scenario: Listener failure aborts caller flow

- **WHEN** listener 抛出异常
- **THEN** Dispatcher SHALL 向调用方传播该异常，且不得运行后续 listener 或自行提交、回滚或重试

#### Scenario: Event and Player mismatch is rejected

- **WHEN** EventContext 的 Player ID 与 event.player_id 不相同
- **THEN** Dispatcher SHALL 在执行任何 listener 前拒绝派发

### Requirement: Built-in player and virtual account events have defined timing

系统 SHALL 提供 `PlayerConstructedEvent`、`PlayerDeconstructingEvent` 和 `VirtualAccountLoggedInEvent`。Construct event SHALL 在玩家 Construct 标记已取得、初始化聚合已加载后且所在 Auth transaction 提交前派发；Deconstructing event SHALL 在删除 Player 数据前派发；VirtualAccountLoggedIn event SHALL 在有效虚拟账号成为当前账号后、所在普通 Operation transaction 提交前派发。各事件 SHALL 包含 player_id 和 occurred_at；Construct event SHALL 包含 `registration` 或 `first_login` trigger，Deconstructing event SHALL 包含 `deletion` trigger，虚拟账号登录事件 SHALL 包含 account_id。

#### Scenario: Construct listener replaces lifecycle construct handler

- **WHEN** 新注册玩家或首次登录的 legacy 玩家触发 Construct
- **THEN** 系统 SHALL 在同一 Auth transaction 内派发 `PlayerConstructedEvent`，且 listener 修改随 Auth transaction 提交或回滚

#### Scenario: Guest virtual-account login produces a typed event

- **WHEN** 玩家使用有效凭据登录虚拟账号 `example.guest`
- **THEN** 系统 SHALL 在该 `/vac/login` Operation transaction 内派发 account_id 为 `example.guest` 的 `VirtualAccountLoggedInEvent`

#### Scenario: Failed account login produces no event

- **WHEN** 虚拟账号凭据无效，或账号登录 Operation 因任意原因回滚
- **THEN** 系统 SHALL NOT 成功派发或持久化该次 `VirtualAccountLoggedInEvent` 的 listener 写入

### Requirement: EventBus is not a durable or asynchronous messaging system

EventBus SHALL 仅提供当前进程内、当前调用栈内、同步 await 的监听器派发。系统 SHALL NOT 为 EventBus 持久化事件、使用消息代理、跨进程传递、自动重试、延迟调度、死信处理或提供 HTTP callback 路由。

#### Scenario: Completed transaction does not schedule deferred delivery

- **WHEN** 包含事件派发的调用方 transaction 已提交
- **THEN** 系统 SHALL 不因该事件创建后台投递、重试任务或延迟 listener 执行

### Requirement: Legacy lifecycle API is removed

系统 SHALL 移除 LifecycleRegistry、LifecycleCatalog、PlayerLifecycleDispatcher、`registries.lifecycle`、`on_construct` 和 `on_deconstruct` 注册 API。原 Construct 和 Deconstruct 监听器 SHALL 使用 EventRegistry 中对应的 typed event listener 注册。

#### Scenario: Puzzle migrates a construct listener

- **WHEN** 谜题模块需要响应玩家 Construct
- **THEN** 模块 SHALL 注册 `PlayerConstructedEvent` listener，不得调用已移除的 lifecycle API
