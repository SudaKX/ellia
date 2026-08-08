## Why

Mythos 需要支持按玩家状态执行的时间相关逻辑，例如延迟解锁、资源结算和过期处理。当前后端没有持久化的任务类型、玩家任务状态或统一执行入口；使用每秒轮询会引入额外常驻调度器、重复执行风险和多进程协调问题，也不符合玩家只在请求时需要状态更新的场景。

本变更引入请求触发的惰性任务执行：任务只在登录、Construct、已认证写命令或显式处理请求中被检查，时间计算和业务动作由注册的异步 Handler 决定。

## What Changes

- 新增 TaskRegistry 和冻结后的 TaskCatalog，允许模块注册带稳定任务身份、异步 Handler 和 PlayerInterface 依赖的任务类型。
- 新增玩家任务状态持久化，保存 `player_id`、`task_id`、`time_1`、`time_2`、错误次数和 JSON `meta`。
- 新增 `Player.tasks` Interface，支持在事务内为指定玩家幂等添加和移除已注册任务。
- 新增 TaskContext 状态修改 API；Handler 正常完成时由执行器自动更新 `time_1`，Handler 可设置 `extra_time`、修改 `meta` 或声明本次延后完成。
- 新增 TaskExecutor，按当前玩家任务记录加载 Handler 依赖的 Interface，并在一个 Task 事务中执行任务。
- 为每个 Handler 提供保存点回滚；可识别的 Handler 错误只回滚当前 Handler 并增加错误次数，任务外层事务、数据库、序列化、Hook 和提交错误直接终止请求。
- 新增 `execute_with_task`，在一次 Request-ID 生命周期内先提交独立的 Task 事务，再提交 Operation 事务；Operation 失败不回滚已提交的 Task 状态。
- 新增基于注册身份集合的 Task Registry Snapshot，启动时移除当前 Catalog 中不存在的玩家任务记录，并在清理成功后更新 Snapshot。
- 新增显式处理到期任务的 HTTP 命令接口和任务状态读取接口；处理报告包含每个任务的成功/失败状态，不暴露任意 Handler Callback 路由。
- 更新持久化、事务、Player Interface、API 和运维文档，并补充任务调度、错误和并发测试。

## Capabilities

### New Capabilities

- `lazy-task-execution`: 定义 TaskRegistry、玩家任务状态、惰性执行时机、TaskContext、任务事务、任务快照和 HTTP/Interface 契约。

### Modified Capabilities

无。

## Impact

- 运行时组装：`RegistryBundle`、`RuntimeCatalogs`、`ApplicationRuntime`、`ServiceContainer` 和 lifespan 启动 reconciliation。
- 持久化：新增玩家任务 ORM Model、Alembic migration、JSON `meta` 编解码和任务状态索引。
- Player：新增任务 Interface、任务添加/移除操作和依赖 Interface 的批量加载。
- 命令事务：新增 `execute_with_task` 的 Request-ID 编排、Task 前置事务和失败边界。
- HTTP：新增 `/api/v1/tasks` 读取与处理端点，继续使用 `/api/v1`、Bearer JWT 和命令 `Request-ID` 约定。
- 模块注册：新增独立于 access rule 的异步 Task Handler 装饰器；任务依赖只保存在冻结 Catalog 的运行时 Handler 元数据中，不复制到玩家任务行。
- 部署与运维：启动前必须执行新增 migration；Task Snapshot 清理依赖当前 Catalog，空 Catalog 和 Snapshot 损坏需要阻止应用进入 ready。
