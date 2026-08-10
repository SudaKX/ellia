## 1. Context 基础模型

- [ ] 1.1 定义统一 `Context` 基类，使所有实际 Context 直接持有 `player` 和 per-call `ContextScope`
- [ ] 1.2 删除只承载 `player` 的 `PlayerContext` 中间层，迁移 `RequestContext`、`CommandContext` 和 `PlayerLifecycleContext` 的继承与构造
- [ ] 1.3 让可变 `TaskContext` 复用统一 Context 初始化，同时保留任务状态字段和可变 meta/defer 语义
- [ ] 1.4 实现 Context 子类的 `from_context()` 或等价显式构造，验证子 Context 共享同一个 scope identity

## 2. Core Followup 与 Scope

- [ ] 2.1 定义 transport-neutral 的 `Followup`、`FollowupSink`、`FollowupCollector`、`NullFollowupSink` 和 `ContextScope`
- [ ] 2.2 将 Followup 收集逻辑从 FastAPI JSON 编码中分离，确保 Core Followup 模块不导入 FastAPI
- [ ] 2.3 为 HTTP 请求、非 HTTP Workflow 和测试提供 collecting/silent scope 创建方式
- [ ] 2.4 让 `Context.followup()` 通过共享 scope 写入 sink，并验证多个 Context 的顺序收集与请求间隔离

## 3. Endpoint 与 Task Scope 传播

- [ ] 3.1 让 `EndpointCommandExecutor` 为一次逻辑请求创建 HTTP collecting scope，并在 Task phase 与 Operation Context 之间复用
- [ ] 3.2 让 `TaskCommandExecutor` 传播 HTTP scope，并将 TaskContext Followup 合并到 Task-only 响应
- [ ] 3.3 让 `TaskService.run_itx()` 接收 per-call ContextScope，非 HTTP 调用默认使用 silent scope，且 Service 不依赖 HTTP Context
- [ ] 3.4 让 Lifecycle、Task 和其他内部 Context 在需要时复用调用方 scope，不把 request-specific sink 存入 Runtime 或共享 Pipeline
- [ ] 3.5 将 Followup JSON 编码、JSON object 校验和响应包装移动到 Endpoint/Response adapter，并保持现有响应 body 结构

## 4. ValidationContext 迁移

- [ ] 4.1 定义 `ValidationContext`、`ValidationRejected` 和 `ValidationResult`，并更新 Validation Handler 类型合同
- [ ] 4.2 将 `ValidationService.submit()` 改为接收 Player/ValidationAttempt/payload，不再依赖 `CommandContext`、Request-ID 或 ResponseSpec
- [ ] 4.3 将 Validation Handler 的 reject 改为不接收 status code 的领域 `reject(reason, details)`
- [ ] 4.4 将所有 `ValidationRejected` 在 Endpoint 固定转换为 HTTP `409 Conflict`，并为其他 HTTP 状态保留独立异常路径
- [ ] 4.5 迁移 Example Validation、Validation Endpoint 和现有 Validation 测试，保持 accepted/followups/Problem Details 的外部契约

## 5. 文档、边界与验证

- [ ] 5.1 更新 Context、Followup、Validation 和 Task 架构文档，明确 HTTP collecting 与非 HTTP silent 语义
- [ ] 5.2 更新 Validation API/系统文档，删除 Handler 自由指定 HTTP status 的旧描述
- [ ] 5.3 增加 HTTP Task/Operation followup、silent Workflow、Validation 无 CommandContext 和固定 409 映射测试
- [ ] 5.4 增加 Context scope identity、Context 构造和非 FastAPI 依赖边界测试
- [ ] 5.5 运行 OpenSpec 规定的聚焦测试和完整 Mythos 测试目录，确认 RustFS 集成测试按环境开关执行
