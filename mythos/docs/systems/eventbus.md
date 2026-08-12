# 进程内事件总线

模块通过 `registries.events.on(EventType, priority=...)` 注册异步 listener。注册的 listener 必须使用 `module_handler` 声明所需的 Player Interface；EventRegistry 在启动期冻结为只读 Catalog，并按 `EARLY`、`DEFAULT`、`LATE` 与注册顺序保存 listener。Dispatcher 只匹配事件的精确类型。

`EventContext` 提供不可变 event、调用方已加载的可写 `Player` 和调用方 scope。Dispatcher 不持有 Session、不加载或锁定 Player、不提交或回滚 transaction；listener 的写入属于调用方现有 transaction，任一 listener 异常会中止后续 listener 并向调用方传播。

当前内置事件包括：

- `PlayerConstructedEvent`：注册时，或既有玩家的首次真实登录补偿 Construct 时，在 Auth transaction 提交前派发；其 trigger 为 `registration` 或 `first_login`。
- `PlayerDeconstructingEvent`：为未来玩家删除 workflow 预留；应在删除 PlayerRecord 前派发，当前没有公开删除 Router。
- `VirtualAccountLoggedInEvent`：虚拟账号有效登录并成为当前账号后，在 `/vac/login` 的 Operation transaction 提交前派发。

EventBus 仅为当前进程、当前调用栈中的同步 `await` 扩展点。它不持久化事件，不使用消息代理，不跨进程传递，不提供重试、延迟调度、死信队列或 HTTP callback 路由。
