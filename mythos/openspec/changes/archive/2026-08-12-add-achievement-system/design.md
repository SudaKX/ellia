## Context

Mythos 当前已经有冻结式 Registry、Player Interface、PlayerLoader、RequestCache、PipelinedTransaction，以及 Task/Operation 的命令事务边界，但尚未实现 Achievement 领域。现有临时设计要求 Achievement 读取当前冻结 Catalog，持久化玩家达成状态，并把普通写命令后的检查和奖励拆成 Operation 提交后的独立补偿事务。

实现必须遵守现有仓库边界：全局 Service 不提交调用方 Session；HTTP 普通命令由 `EndpointCommandExecutor` 组织；Task-only 命令由 `TaskCommandExecutor` 组织；Auth Workflow 不执行 Task 或 Achievement；Registry 内容在启动 freeze 前完成注册。

## Goals / Non-Goals

**Goals:**

- 提供 puzzles Registry 注册 Achievement definition 的框架能力；本 change 不修改具体 puzzle 内容。
- 用稳定的 HMAC public ID 暴露成就定位符，但不将 public ID 或定义副本写入玩家状态表。
- 持久化玩家达成和领取状态，支持活动成就与已删除成就 fallback 的统一查询。
- 在普通写命令 Operation 提交后执行独立 Check transaction 和 Effect transaction。
- 支持 immediate effect、显式 `/achievement/check` 补偿和 `/achievement/claim/{public_id}` 领取。
- 在 Check/Effect 失败时保留 Operation 结果，使用 `warn` 完成 RequestCache。

**Non-Goals:**

- 不在 Auth Workflow 或 `/tasks/process` 中自动执行 Achievement。
- 不新增后台 worker、队列、Outbox 或通用 callback HTTP 路由。
- 不支持已删除成就的 condition、effect、claim 或补领。
- 不在玩家成就状态表中复制 meta、immediate、public_id 或回调代码。

## Decisions

### Registry 与 Catalog

新增 `AchievementRegistry` 和冻结后的 `AchievementCatalog`，注册项声明 `stable_id`、`immediate`、JSON `meta`、同步 condition、异步 effect 及 Player Interface 依赖。`public_id` 由框架从 stable ID 派生，模块不自由填写。

Catalog 在 `RegistryBundle.freeze()` 时生成，只读提供 stable ID、public ID、全部活动定义和版本指纹查询。依赖在 freeze 前校验，运行时通过已冻结 Catalog 读取。

### Public ID

复用现有 file-ID signing key，使用独立域：

```text
a1_ + Base64URL(HMAC-SHA256(file_id_secret, "achievement:v1\\0" + stable_id))
```

Achievement ID 不复用 file 或 hint 域，也不作为授权凭据。数据库不保存 public ID，因此密钥轮换会使旧 ID 失效，保持与现有 file ID 协议一致。

### 持久化与状态

新增 `player_achievement_states`，复合主键为 `(player_id, achievement_stable_id)`，只保存 `earned_at`、可空 `claimed_at` 和审计时间。无记录表示 `locked`，有 earned 无 claimed 表示 `available`，有 claimed 表示 `claimed`。

活动成就的定义字段来自当前 Catalog；历史记录通过 `AchievementRegistry` 在 freeze 前配置的 data-only fallback 补充展示字段。相同 stable ID 的 fallback 后续注册会覆盖前值，freeze 时的最后数据进入只读 Catalog。fallback 不接受 condition/effect，当前 Catalog 与 fallback 冲突时启动失败。

### Player Interface 与 Service

新增 `PlayerInterfaces.ACHIEVEMENTS`、`Player.achievements` 和 PlayerLoader 加载入口。Interface 只管理状态记录，不打开或提交 transaction，也不执行回调。

`AchievementService` 是全局事务中立 Service，接收调用方提供的 Player、冻结 Catalog 和当前 Session。它不能依赖 FastAPI、RequestCache 或 Endpoint Executor。

### 事务编排

普通写命令保持现有 Task A、Operation B 边界；B 提交后由 CommandExecutor 继续执行：

```text
Task A -> commit
Operation B -> commit
Achievement Check C -> commit
Achievement Effect D -> commit
final response + warn -> RequestCache
```

C transaction 执行全部 condition 并写 earned records；任一 condition 或 C hook 异常回滚 C，不启动 D，生成 warning 并完成缓存。`condition == false` 不是错误。

D transaction 执行全部需要发放的 effect，并处理领取状态；任一 effect 或 D hook 异常回滚整个 D，保留已提交的 C earned records，生成 warning 并完成缓存。C/D 不使用 per-effect savepoint。

Achievement C/D 的异常由 CommandExecutor 边界捕获，不能影响已经提交的 Operation B。普通主事务 A/B 的异常继续使用现有 Problem Details 和 lease release 语义。

### HTTP API

新增：

- `GET /api/v1/achievement`：只读返回活动成就和历史 fallback 合并后的状态。
- `POST /api/v1/achievement/check`：独立 AchievementCommandExecutor，执行 C 后 D。
- `POST /api/v1/achievement/claim/{public_id}`：只允许当前活动、已达成且未领取的成就执行 effect；已删除成就不可领取。

所有写接口要求 Bearer JWT、UUID Request-ID，并遵循现有 RequestCache replay 语义。C/D 失败仍返回原始命令结果并附带安全的 `warn`，不暴露异常细节。

## Risks / Trade-offs

- [Effect 非原子外部副作用] → Effect 只能使用现有事务内 Player Interface；外部不可逆副作用不纳入本变更。
- [HMAC 密钥轮换使旧 public ID 失效] → 将 file-ID signing key 视为稳定协议密钥，并在文档中明确轮换影响。
- [Catalog 删除后缺少历史展示定义] → 缺少 fallback 时使用空 `meta`，仍返回历史状态和派生 public ID，并禁止 claim。
- [C 成功而 D 失败造成 available 状态] → 保留 earned record，使用 `/achievement/check` 重试 effect。
- [多个成就 effect 的失败顺序] → D 使用单个 batch transaction；任一 effect 失败整体回滚，不继续执行后续 effect。
- [请求缓存与补偿重复执行] → C/D 完成后才 `lease.complete()`；补偿接口使用独立 Request-ID，已完成 Request-ID 只 replay。

## Migration Plan

1. 增加成就状态表迁移，不修改已有玩家或 Task 数据。
2. 启动时注册并冻结 Achievement Catalog，配置 data-only fallback。
3. 发布查询接口和 Registry/Player Interface，再接入普通写命令的 C/D 编排。
4. 最后启用 immediate effect、check 和 claim 的完整 HTTP 行为。
5. 回滚代码时保留新增表和历史记录；旧版本不读取它们，不删除已达成数据。

## Resolved Decisions

- 缺少 fallback 的已删除成就在查询响应中使用空 `meta`；其状态仍由 PlayerAchievementState 决定，不能 claim。
- Achievement warning 保持简洁，由最终 `ResponseSpec` warning 类型约束；实现可以在基础字段上补充必要上下文，不在本 design 中锁定过细字段集合。
- 本 change 不修改任何具体 puzzle；只实现 Registry/Catalog 框架、接入点和测试夹具。
