## 1. 持久化模型与迁移

- [x] 1.1 新增 `PlayerTaskState` ORM Model，使用 `(player_id, task_id)` 复合主键、玩家级联外键、时间字段、非负 `exception` 和 JSON `meta` 文本字段
- [x] 1.2 为 `player_task_states.task_id` 创建启动清理所需索引，并补充字段长度、非负值和默认值约束
- [x] 1.3 创建下一版本 Alembic migration，并验证升级、降级和从已有玩家数据库迁移的行为
- [x] 1.4 将任务 Model 导出到 persistence models 聚合入口，并更新持久化 schema 文档

## 2. TaskRegistry 与 TaskCatalog

- [x] 2.1 新增独立于 access rule 的异步 Task Handler 装饰器，校验 Handler 签名、稳定任务身份和 `PlayerInterfaces` 依赖
- [x] 2.2 新增 TaskRegistry、TaskDefinition 和 TaskCatalog，提供注册、冻结、身份查找和依赖元数据索引
- [x] 2.3 将 TaskRegistry 加入 RegistryBundle 和 RuntimeCatalogs，并确保 freeze 后拒绝新的任务注册
- [x] 2.4 为 TaskCatalog 实现仅包含注册身份集合和指纹的 Snapshot 数据结构
- [x] 2.5 为 TaskCatalog 增加当前有效任务身份查询，供 `add_task()` 校验和启动 reconciliation 使用

## 3. Player Task Interface 与 Context

- [x] 3.1 新增 `TaskInterface`，支持任务状态读取、幂等 `add_task()` 和 `remove_task()`，并拒绝只读 Player 的写入
- [x] 3.2 将 TaskInterface 加入 Player、PlayerFactory 和 `PlayerInterfaces` 选择机制，支持任务依赖 Interface 的批量加载
- [x] 3.3 实现 TaskContext，提供只读任务输入、统一 UTC 当前时间、`set_extra_time()`、meta 更新和 `defer()` 操作
- [x] 3.4 实现严格 JSON meta 编解码、大小限制和异常路径下的 Context 状态丢弃
- [x] 3.5 验证 Handler 删除当前任务、新增任务和重复增删时的事务内语义

## 4. TaskExecutor 调度与事务

- [x] 4.1 实现 TaskExecutor，按任务键快照查找当前 TaskCatalog Handler 并求依赖并集
- [x] 4.2 实现正常路径复用单个 writable Player，并在 Handler 保存点回滚后重载 Player 后继续本轮剩余任务
- [x] 4.3 使用 `session.begin_nested()` 隔离单个 Handler 的可识别错误，回滚其 PlayerInterface 修改、增加 `exception` 并记录逐任务失败状态
- [x] 4.4 实现 Handler 正常返回时自动更新 `time_1`、保存 `extra_time` 和 meta；处理 `defer()` 及当前任务被删除的情况
- [x] 4.5 区分 `TaskHandlerError` 与数据库、序列化、保存点、Hook、提交和取消异常；复杂外层失败直接抛出并跳过 Operation
- [x] 4.6 接入现有 pre-commit hook，支持任务触发 checkpoint、Artifact 等既有提交行为，并验证 Hook 失败时 Task transaction 直接失败

## 5. CommandExecutor 编排

- [x] 5.1 在 `CommandTransactionExecutor` 中增加一次 Request-ID 生命周期内的 `execute_with_task()` 编排入口
- [x] 5.2 让 `execute_with_task()` 先提交 Task transaction，再以新加载的 Player 执行 Operation transaction
- [x] 5.3 确保已完成 Request-ID 在 Task transaction 启动前直接返回缓存响应，失败时正确释放 Request-ID
- [x] 5.4 为生命周期内部的 `execute_nocache_itx()` 增加关闭自动任务阶段的能力，避免 Construct 递归触发任务
- [x] 5.5 为登录、注册/Construct、普通写命令和显式处理命令接入统一 TaskExecutor，验证各触发点不会重复执行

## 6. 启动 Snapshot Reconciliation

- [x] 6.1 新增 Task Snapshot Store，复用现有 SnapshotStore 的严格解析、临时文件和原子替换能力
- [x] 6.2 新增启动 reconciliation，删除当前 TaskCatalog 不存在的 `player_task_states`，并在清理成功后写入新 Snapshot
- [x] 6.3 增加空 Catalog、Snapshot 损坏、缺失任务表和多次启动幂等处理
- [x] 6.4 在应用 lifespan 中按 Catalog freeze、TaskExecutor 创建、任务清理、ServiceContainer 组装的顺序接入

## 7. HTTP 与运行时 Service

- [x] 7.1 新增全局 TaskService 或等价运行时 Service，提供任务状态快照和显式处理报告
- [x] 7.2 新增 `GET /api/v1/tasks`，只读取当前玩家任务状态，不触发任务写入
- [x] 7.3 新增 `POST /api/v1/tasks/process`，要求 Bearer JWT、UUID `Request-ID`、使用任务事务并返回逐任务成功/失败状态
- [x] 7.4 验证错误响应、Request-ID 重放、执行中冲突和不暴露通用 Callback 路由
- [x] 7.5 更新 API 索引、命令契约、架构文档和任务系统领域文档

## 8. 测试与验证

- [x] 8.1 测试 TaskRegistry Handler 注册、异步签名校验、重复身份和 freeze 后不可变行为
- [x] 8.2 测试任务行添加、重复添加、删除、只读拒绝、meta 编解码和级联删除
- [x] 8.3 测试 `time_1` 自动更新、`extra_time`、`defer()`、当前任务删除和新任务延迟到下一轮执行
- [x] 8.4 测试多个任务的依赖并集、正常 Player 复用、Handler 失败后的保存点回滚、Player 重载和后续任务继续执行
- [x] 8.5 测试 Task transaction 与 Operation transaction 的独立提交、Operation 失败保留任务状态和 Request-ID 重放不重复执行
- [x] 8.6 测试 Task 外层数据库、JSON、Hook、提交和取消异常直接抛出且不启动 Operation
- [x] 8.7 测试任务 Handler 触发 checkpoint、Artifact 等 pre-commit hook 时的成功提交、保存点回滚和 Hook 失败行为
- [x] 8.8 测试 Snapshot 新增/移除身份、失效任务清理、空 Catalog 保护和 Snapshot 原子写入
- [x] 8.9 运行 Mythos 完整测试目录，并针对任务、命令事务、生命周期和迁移执行聚焦测试
