## 1. EventBus 基础设施

- [x] 1.1 新增 `eventbus` 包的不可变 Event、PlayerEvent、EventContext、EventPriority 和首批 Construct、Deconstructing、VirtualAccountLoggedIn 事件定义。
- [x] 1.2 实现 EventRegistry、冻结 EventCatalog 及 listener 的类型、异步签名、依赖声明、重复注册、priority 和稳定顺序校验。
- [x] 1.3 实现事务中立 EventDispatcher，校验 Player/Event ID 对应关系并按精确类型、有序同步派发 listener。
- [x] 1.4 将 EventRegistry 和 EventCatalog 接入 RegistryBundle、freeze 流程与 RuntimeCatalogs，并暴露事件类型的依赖并集查询。

## 2. Runtime 与发布点迁移

- [x] 2.1 在应用启动期构造 EventDispatcher 并挂载到 ApplicationRuntime，不加入 ServiceContainer。
- [x] 2.2 将 Auth Construct workflow 从 PlayerLifecycleDispatcher 迁移为在既有 Auth transaction 中派发 PlayerConstructedEvent，并按事件依赖加载 Player。
- [x] 2.3 将玩家删除前的 lifecycle 逻辑迁移为 PlayerDeconstructingEvent，确认 listener 在关联数据删除前运行。
- [x] 2.4 在 `/vac/login` 的 Operation 中于 AccountService 登录成功后派发 VirtualAccountLoggedInEvent，并以事件依赖扩展 Player 加载接口。
- [x] 2.5 保持 AccountService、AchievementService 和其他 Domain Service 不依赖 EventDispatcher、Session ownership、HTTP 或 Request-ID。

## 3. 移除旧 Lifecycle API

- [x] 3.1 将所有框架和 puzzles 的 `on_construct` / `on_deconstruct` 注册迁移为 typed EventBus listener，并保留原有优先级和执行顺序。
- [x] 3.2 删除 `registry/lifecycle`、`services/lifecycle`、PlayerLifecycleContext 及其导出、Runtime 字段和旧注册入口。
- [x] 3.3 更新相关类型注释、模块导入和文档，确保仓库中不再引用已删除 lifecycle API。

## 4. 测试与验证

- [x] 4.1 添加 EventRegistry/Catalog 测试，覆盖合法注册、freeze、非法 listener、缺少依赖、重复注册和 deterministic ordering。
- [x] 4.2 添加 EventDispatcher 测试，覆盖精确类型匹配、Player/Event ID 不匹配、监听器写入参与外层 transaction，以及异常传播后不运行后续 listener。
- [x] 4.3 更新 Auth、玩家生命周期和虚拟账号测试，覆盖 Construct、Deconstructing、成功虚拟账号登录的事件时序与失败登录无 listener 写入。
- [x] 4.4 运行 `mythos/.venv` 的成就、账户、生命周期相关聚焦测试及完整 `tests` 套件。
- [x] 4.5 运行 `openspec validate generalize-lifecycle-to-eventbus --strict`，并确认本 change 未包含主动成就 grant 或持久化消息系统实现。
