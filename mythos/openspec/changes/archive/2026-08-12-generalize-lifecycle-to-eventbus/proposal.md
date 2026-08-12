## Why

现有 LifecycleRegistry 只表达 Player Construct/Deconstruct，然而虚拟账号登录等同样需要由谜题模块响应的事务内领域事件已经出现。继续向 lifecycle 追加非生命周期事件会使名称、职责和扩展方式失真，并阻碍主动成就授予等后续能力。

## What Changes

- 新增冻结式、进程内的 EventBus Registry、Catalog 和 Dispatcher，允许模块按事件类型注册有序异步监听器。
- 提供通用事件与上下文模型；事件携带不可变业务数据，监听器通过调用方已加载的 Player 和既有事务写入状态。
- 将 Construct/Deconstruct 生命周期事件迁移为 EventBus 事件，并移除旧 `registry/lifecycle` 与 `services/lifecycle` 实现。
- 新增虚拟账号登录事件，使模块可在成功切换账号的同一 Operation transaction 中响应。
- **BREAKING** 旧 `registries.lifecycle.on_construct` / `on_deconstruct` 注册 API 和 `PlayerLifecycleDispatcher` 将被移除，模块改为向 `registries.events` 注册对应事件监听器。
- 明确 EventBus 不提供持久化投递、后台调度、跨进程传播、重试或外部副作用补偿。

## Capabilities

### New Capabilities
- `in-process-eventbus`: 冻结式事件注册、同步事务内派发、监听器校验、顺序和失败语义，以及内置 Player 和虚拟账号事件。

### Modified Capabilities
- `command-execution-boundaries`: 普通 Player Operation 可在提交前同步派发领域事件；监听器写入参与调用方 transaction，失败回滚该 Operation。
- `context-followup-propagation`: 移除 PlayerLifecycleContext，EventContext 改为复用调用方提供的 Player 与 ContextScope。

## Impact

- 受影响代码包括 `registry/bundle`、新的 `eventbus` 包、ApplicationRuntime 组装、Auth Construct workflow、虚拟账号操作、Player context、puzzles Example 注册和相关测试。
- 不新增 HTTP 路由、数据库表、消息代理或第三方依赖。
- 后续主动成就 grant change 将消费 `VirtualAccountLoggedInEvent`，但不属于本 change 的实现范围。
