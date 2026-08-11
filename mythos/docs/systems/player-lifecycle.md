# 玩家生命周期系统

模块通过 `registries.lifecycle.on_construct` 和 `on_deconstruct` 注册异步回调。框架事件使用固定数字 ID：Construct 为 `1`，Deconstruct 为 `2`；优先级仅可为 `EARLY`、`DEFAULT`、`LATE`。冻结 Catalog 按优先级和注册顺序直接保存 handler 容器，Dispatcher 在事务内顺序调用。

Construct 在新玩家注册时触发；`players.constructed_at` 为空的既有玩家会在首次真实登录时补偿触发。事务会先以条件更新声明 Construct 执行权；回调或 pre-commit hook 失败时该标记随注册或登录事务回滚，之后可重试。

`PlayerLifecycleContext` 提供事件和可写 `Player`，模块可以发放虚拟账号、推进进度或生成 Artifact，但不能访问 Session。Deconstruct 尚无公开 Router；未来玩家删除服务会在删除 `PlayerRecord` 前触发它。
