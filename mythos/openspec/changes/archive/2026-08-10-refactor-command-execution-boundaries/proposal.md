## Why

`CommandTransactionExecutor` 当前同时负责 Request-ID 缓存、Player 行锁与加载、事务边界、CommandContext、响应封装、Task 阶段和 Pipeline Hook，导致 HTTP 命令、Auth Workflow、启动 reconciliation 与 Domain Service 共享了不清晰的职责边界。成就系统需要在普通命令、Task、认证和补偿流程中复用事务与 Player 状态能力，因此现在需要先把通用执行基础设施从 HTTP 命令适配器和 `core` 模块中抽离。

## What Changes

- 新增独立的命令执行基础设施模块，抽离带自动清理的 Request-ID lease、Player 行锁与 Player 加载、单 transaction Pipeline/Hook 执行等能力；事务边界直接使用调用方的 `AsyncSession.begin()`。
- **BREAKING** 将现有 `core/commands` 移出 `core`，建立独立的顶层 commands/application 边界，并更新内部导入。
- 将普通 HTTP 写命令统一收敛到 `EndpointCommandExecutor`；默认命令 Pipeline 执行 Task 前置阶段，并为后续 Achievement 检查和 effect 提供阶段接入点。
- 将 `execute_tasks()` 这类 Task-only HTTP 命令移出通用 Player Operation Executor，由 Task 专用命令适配器组合通用 Request/Transaction 基础设施。
- 将任务领域执行能力并入 `TaskService`；`TaskService.run_itx()` 只参与调用方提供的 transaction，禁止自行开启、提交或回滚外层事务。
- 抽出可被 Task、Achievement、Auth Workflow 和 reconciliation 复用的 `PlayerLoader`，统一玩家行锁与 writable Player 加载行为；PlayerInterfaces 归入 `players/interfaces/` 并由 package 入口重新导出。
- 将各领域 Router 从 `services/*` 子包迁移到统一的 `endpoints` 子包；Domain Service 不再依赖 FastAPI、RequestCache 或 `EndpointCommandExecutor`。
- 将 AuthService 明确作为独立 Auth Workflow，继续协调认证表、Construct 和 Task，但使用原生 `session.begin()`、PlayerLoader 和事务内 TaskService，而非 HTTP 命令适配器。
- 将单 transaction Pipeline 重命名为 `PipelinedTransaction`，由 Runtime 初始化一个配置固定的应用级实例；Pipeline operation、phase 和 hook 直接接收 `session` 与 `player`，不再创建 `PipelineContext`。
- 将 `TaskCommandExecutor` 与 `EndpointCommandExecutor` 放入同一个 `commands/executor.py` 模块；保留两个类的职责边界，不合并普通 Player Operation 与 Task-only HTTP 语义。
- 保持现有 `/api/v1` 路由路径和 Request-ID HTTP 语义不变；本变更主要调整内部模块边界和调用方式。
- 补充架构约束、Task 执行语义、Endpoint Pipeline 和内部 Workflow 的测试与文档。

## Capabilities

### New Capabilities

- `command-execution-boundaries`: 定义 Request 缓存 lease、显式 Session transaction、PlayerLoader、EndpointCommandExecutor、PipelinedTransaction 和 Domain Service/Workflow 的职责边界。

### Modified Capabilities

- `lazy-task-execution`: 修改普通 HTTP 写命令的默认执行入口和 Task-only 命令编排方式，明确内部 Workflow 可在自己的外层事务中调用 TaskService。

## Impact

- 影响 `core/commands`、`players/interfaces/selection.py`、`core/runtime.py`、`main.py`、`PlayerLoader`、`TaskService`、PipelinedTransaction 和所有当前 Router。
- 新增 `commands`、`endpoints` 及必要的 Workflow/PlayerLoader 模块；最终只保留一个命令 Executor 模块。
- 影响 AuthService、Task/Artifact/Account reconciliation 的事务调用方式。
- 影响 ServiceContainer、ApplicationRuntime 和应用启动期依赖组装。
- 需要更新所有相关测试、架构文档、Task OpenSpec 和 Agent 约束。
- 不在本变更中实现完整 Achievement Registry、持久化模型或具体 Achievement 定义；只提供其后续接入所需的执行边界。
