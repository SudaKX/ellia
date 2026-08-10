> 1-8 记录基础边界迁移及其验证，已完成。第 9 节记录本轮设计收敛后的额外简化。

## 1. 基础包与依赖边界

- [x] 1.1 创建顶层 `mythos.commands` 包，定义基础设施、Pipeline 和 `EndpointCommandExecutor` 的模块边界
- [x] 1.2 将 `RequestCache`、Request-ID 异常和 CachedResponse 相关类型迁移到 commands 边界，并更新内部导入
- [x] 1.3 为 commands、endpoints、services 和 workflows 建立依赖方向测试或静态检查

## 2. Transaction scope 与 PlayerSession

- [x] 2.1 实现显式拥有 transaction 的 `async with transaction_scope(session)`，正常退出提交、异常退出回滚；不新增隐式 `run_itx()` 事务包装
- [x] 2.2 实现 PlayerSession，统一 PlayerRecord 行锁、PlayerFactory 创建和 Interface 加载
- [x] 2.3 将 CommandTransactionExecutor 的 Player 加载/锁定逻辑迁移到 PlayerSession
- [x] 2.4 将 TaskExecutor 的 Player 锁定和加载逻辑迁移到 PlayerSession，并保留 Handler savepoint 后的 Player 重载语义
- [x] 2.5 增加 Player 不存在、只读加载、可写锁定、Interface 依赖加载和重载行为测试

## 3. 单 transaction 命令 Pipeline

- [x] 3.1 定义不依赖 FastAPI 的 Pipeline Context、单 transaction 阶段类型和有序 pre-commit hook 接口
- [x] 3.2 实现有限的 Player Operation、post-operation 和 pre-commit 阶段组合
- [x] 3.3 保证 Pipeline 阶段异常回滚当前 transaction，且不暴露任意客户端 Callback 调用能力
- [x] 3.4 为后续 AchievementChecker 预留 post-operation 阶段，但不实现成就领域逻辑

## 4. EndpointCommandExecutor

- [x] 4.1 将现有普通 `execute_with_task()` 逻辑迁移为 `EndpointCommandExecutor` 的默认 `execute()` pipeline
- [x] 4.2 为 RequestCache 增加 `with` lease，自动在异常路径 release，并支持多个物理 transaction 共用一个 Request-ID lease
- [x] 4.3 保持 Task transaction 与 Operation transaction 的独立提交、Operation 失败保留 Task 状态和 Request-ID replay 语义
- [x] 4.4 保持 CommandContext、ResponseSpec、followups 和 CachedResponse 的现有响应契约
- [x] 4.5 为补偿或明确 no-task 命令提供受控的 Task phase 关闭方式，并禁止普通业务 Router 默认绕过 Task

## 5. Task-only 命令与 Task Service

- [x] 5.1 实现 TaskCommandExecutor 或等价的 Task endpoint adapter，负责 Task-only Request-ID、transaction 和 TaskRunReport 响应
- [x] 5.2 将现有 `execute_tasks()` 的领域专用报告组装移出通用 Endpoint Player Operation Executor
- [x] 5.3 保证 `POST /api/v1/tasks/process` 不重复执行 Task phase，且 Request-ID replay 不重复运行 Handler
- [x] 5.4 保持 `TaskExecutor.run_itx()` 为不拥有外层 transaction 的事务内 Service 入口
- [x] 5.5 保持 `TaskService` 只提供任务快照和报告读取能力，不接收 Session 或管理 Request-ID

## 6. Auth 与内部 Workflow 迁移

- [x] 6.1 让 AuthService 使用 transaction scope、PlayerSession 和事务内 TaskExecutor，不再依赖 EndpointCommandExecutor
- [x] 6.2 保持注册、Construct、登录、登出认证状态和 Task 的单一外层 transaction 顺序
- [x] 6.3 增加 Auth Workflow 在 Construct/Task/认证写入失败时的完整回滚测试
- [x] 6.4 将 Account、Artifact 和 Task reconciliation 改为使用内部 transaction/Player 基础设施，并继续关闭不适用的 hooks/Task phase
- [x] 6.5 保持启动 reconciliation 的 Catalog 对账、原子 Snapshot 写入和失败回滚行为

## 7. Endpoints 包迁移

- [x] 7.1 创建 `mythos.endpoints` 聚合包并迁移 auth、accounts、files、hints、credits、progress、scripts、validations 和 tasks Router
- [x] 7.2 更新 `main.py`，通过 endpoints 聚合入口挂载现有 `/api/v1` 路由并保持 URL、鉴权和错误响应不变
- [x] 7.3 确保 Domain Service 和 Auth/Workflow 模块不导入 FastAPI Router、RequestCache 或 `EndpointCommandExecutor`
- [x] 7.4 将可行的 HTTP ResponseSpec 构造从 Domain Service 移到 Endpoint，保持现有 JSON response body

## 8. 验证、文档与清理

- [x] 8.1 增加 RequestCache lease、transaction scope、PlayerSession 和 Pipeline 的单元及事务测试
- [x] 8.2 更新普通写命令、Task-only 命令、Request-ID replay 和 Operation 失败场景测试
- [x] 8.3 更新 Auth、Construct、Task、Account 和 Artifact reconciliation 集成测试
- [x] 8.4 运行完整 Mythos 测试目录、迁移测试和 OpenSpec 规定的聚焦测试
- [x] 8.5 更新架构文档、Task 文档、命令 API 文档和 `AGENTS.md` 中的写入边界约束
- [x] 8.6 删除 `core/commands` 旧实现和无调用的兼容路径，确认仓库内不再存在旧 Router 导入或旧 Executor 调用

## 9. 架构简化后续

- [x] 9.1 删除 `commands/transaction.py` 和 `transaction_scope()` 导出，将所有 transaction owner 改为直接使用 `async with session.begin()`，保持 Service 不拥有外层 transaction
- [x] 9.2 将 PlayerSession 合并为 PlayerLoader，令 PlayerLoader 负责 PlayerRecord 行锁、Player 创建、Interface 加载和 reload；补充依赖检查，避免将数据库锁逻辑移入 Player 聚合
- [x] 9.3 将 TaskExecutor、TaskRun、TaskRunReport 和任务领域执行逻辑合并到 TaskService；TaskService 保留不拥有外层 transaction 的 `run_itx(session, player_id)`
- [x] 9.4 将 TransactionPipeline 重命名为 PipelinedTransaction，移除 PipelineContext，使 operation、phase 和 hook 直接接收 session/player，并在 Runtime 初始化固定共享实例
- [x] 9.5 将 TaskCommandExecutor 从 `commands/task.py` 合并到 `commands/executor.py`，保留 EndpointCommandExecutor 与 TaskCommandExecutor 的职责隔离
- [x] 9.6 更新 Runtime、ServiceContainer、Auth Workflow、Endpoint adapter、reconciliation、测试和文档，并运行完整 Mythos 测试目录
- [x] 9.7 将 `PlayerInterfaces` 移到 `players/interfaces/selection.py`，删除 `core/player_interfaces.py` 和旧转出模块，并在 `players/interfaces/__init__.py` 重新导出
