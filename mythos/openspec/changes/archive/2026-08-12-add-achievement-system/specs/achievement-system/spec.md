## ADDED Requirements

### Requirement: Achievement definitions are registered and frozen

系统 SHALL 提供独立的 `AchievementRegistry`。每个注册项 SHALL 包含唯一 `stable_id`、布尔 `immediate`、JSON 可序列化 `meta`、同步 condition、异步 effect 和 Player Interface 依赖。Registry freeze 后 SHALL 拒绝新增或修改注册项，并生成只读 `AchievementCatalog`。

#### Scenario: Register a valid achievement

- **WHEN** puzzles 模块在 Registry freeze 前注册合法 Achievement definition
- **THEN** AchievementCatalog SHALL 在 freeze 后提供该 stable ID 的 definition、依赖和版本指纹

#### Scenario: Reject invalid achievement callbacks

- **WHEN** 模块注册非同步 effect、非同步 condition、错误参数数量或不可序列化 meta
- **THEN** Registry SHALL 拒绝注册并报告定义错误

#### Scenario: Reject registration after freeze

- **WHEN** 模块在 AchievementRegistry freeze 后尝试注册或替换 definition
- **THEN** Registry SHALL 拒绝修改

### Requirement: Achievement public IDs are derived with the shared HMAC key

系统 SHALL 使用现有 file-ID signing key 和独立域 `achievement:v1\\0` 加 stable ID 计算 Achievement public ID。public ID SHALL 使用 `a1_` 前缀和 Base64URL 编码的 HMAC-SHA256 结果。数据库 SHALL NOT 保存 public ID。

#### Scenario: Stable ID produces a deterministic public ID

- **WHEN** RuntimeCatalog 对同一个 stable ID 计算 public ID
- **THEN** 系统 SHALL 在相同 signing key 下返回相同的 `a1_` public ID

#### Scenario: Achievement IDs do not share another ID domain

- **WHEN** 系统同时计算 file、hint 和 achievement public ID
- **THEN** Achievement ID SHALL 使用独立 achievement 域，不得直接复用 file 或 hint 的 HMAC 输入域

### Requirement: Player achievement states persist only earned and claim timestamps

系统 SHALL 新增 `player_achievement_states`，以 `(player_id, achievement_stable_id)` 为复合主键，保存 `earned_at`、可空 `claimed_at`、`created_at` 和 `updated_at`。玩家删除时状态 SHALL 级联删除。表 SHALL NOT 保存 meta、immediate、public_id、condition 或 effect。

#### Scenario: Missing state is locked

- **WHEN** 玩家没有指定 stable ID 的 PlayerAchievementState
- **THEN** 查询 SHALL 返回 `locked`，且不得预创建状态行

#### Scenario: Earned state is available

- **WHEN** 玩家存在 earned_at 且 claimed_at 为空的状态行
- **THEN** 查询 SHALL 返回 `available`

#### Scenario: Claimed state is claimed

- **WHEN** 玩家存在非空 claimed_at 的状态行
- **THEN** 查询 SHALL 返回 `claimed`

### Requirement: Achievement interface and service are transaction-neutral

系统 SHALL 提供 `PlayerInterfaces.ACHIEVEMENTS`、`Player.achievements` 和 PlayerLoader 加载入口。AchievementInterface SHALL 只管理当前 Player 的状态记录。AchievementService SHALL 使用调用方提供的 Session 和 Player，不得提交、回滚、创建 HTTP 响应或管理 Request-ID。

#### Scenario: Load achievement state with a writable Player

- **WHEN** CommandExecutor 加载 writable Player 的 Achievement Interface
- **THEN** Interface SHALL 读取该玩家的状态记录，并允许调用方 transaction 管理后续写入

#### Scenario: Service participates in caller transaction

- **WHEN** AchievementService 创建 earned record 或更新 claimed_at
- **THEN** 修改 SHALL 随调用方 transaction 一起提交或回滚

### Requirement: Deleted achievements use startup-only display fallbacks

系统 SHALL 允许 puzzles 在 Registry freeze 前通过 `AchievementRegistry.set_fallback()` 注册或覆盖 data-only fallback，并 SHALL 以 freeze 时的最后数据为准。Fallback SHALL 提供 stable ID、meta、immediate 和派生 public ID，但 SHALL NOT 提供 condition、effect 或 claim 能力。当前 Catalog 与 fallback stable ID 冲突时 SHALL 在 freeze 时阻止启动。缺少 fallback 时，查询 SHALL 使用空 `meta`，仍返回可计算的 public ID 和玩家历史状态。

#### Scenario: Display a deleted earned achievement

- **WHEN** 玩家状态存在但当前 AchievementCatalog 不包含对应 stable ID，且存在 fallback
- **THEN** 查询 SHALL 使用 Player state 和 fallback 返回历史成就展示数据

#### Scenario: Deleted achievement cannot be claimed

- **WHEN** 客户端对已删除成就请求 claim
- **THEN** 系统 SHALL 拒绝 claim，不得执行 fallback effect 或重新领取

#### Scenario: Deleted achievement without fallback uses empty meta

- **WHEN** 玩家状态存在但当前 Catalog 和 fallback 都不包含对应 stable ID
- **THEN** 查询 SHALL 使用空 `meta` 返回历史状态和派生 public ID，且 SHALL NOT 标记为可 claim

#### Scenario: Fallback is not changed over HTTP

- **WHEN** 客户端尝试创建、修改或删除 fallback
- **THEN** 系统 SHALL 不提供对应 HTTP 路由

### Requirement: Achievement checks run after committed operations

普通写命令 SHALL 在 Operation transaction 提交后执行独立的 Check transaction。Check SHALL 读取当前 Player 状态，执行全部活动成就 condition，并为新达成成就创建 earned record。condition 返回 false SHALL NOT 被视为错误。

#### Scenario: Operation success triggers a check

- **WHEN** 普通写命令的 Operation transaction 成功提交
- **THEN** CommandExecutor SHALL 启动独立 Check transaction 并执行 Achievement condition

#### Scenario: Condition creates an earned state once

- **WHEN** condition 返回 true 且玩家尚无该成就状态
- **THEN** Check transaction SHALL 创建 earned record；重复检查 SHALL 保持幂等

#### Scenario: Condition failure rolls back the check

- **WHEN** condition、状态写入或 Check hook 抛出异常
- **THEN** Check transaction SHALL 整体回滚，不启动 Effect transaction，向最终响应增加 warn，并保持已提交 Operation 不变

### Requirement: Immediate effects and claims run in independent effect transactions

Check 成功后，系统 SHALL 在独立 Effect transaction 中执行本轮 immediate effect，并更新相应领取状态。Effect SHALL 以单个 batch transaction 执行，不使用 per-effect savepoint。Effect 失败 SHALL 回滚整个 Effect transaction，但 SHALL 保留已提交的 earned record。

#### Scenario: Immediate achievement effect succeeds

- **WHEN** 新达成成就 immediate 为 true 且 effect 成功
- **THEN** Effect transaction SHALL 提交 effect 修改和 claimed_at，并返回无 warn 的结果

#### Scenario: One effect failure rolls back the effect batch

- **WHEN** 任一 effect 或 Effect hook 抛出异常
- **THEN** 整个 Effect transaction SHALL 回滚，后续 effect SHALL NOT 执行，earned record SHALL 保留，最终响应 SHALL 包含 warn

#### Scenario: Non-immediate achievement remains claimable

- **WHEN** 新达成成就 immediate 为 false
- **THEN** Check SHALL 保留 available 状态，不得自动执行 effect

### Requirement: Achievement HTTP APIs expose query, check and claim

系统 SHALL 暴露 `GET /api/v1/achievement`、`POST /api/v1/achievement/check` 和 `POST /api/v1/achievement/claim/{public_id}`。写接口 SHALL 要求 Bearer JWT 和 UUID Request-ID，并 SHALL 使用现有 RequestCache replay 语义。Achievement warning SHALL 使用最终 ResponseSpec 定义的简洁 warning 类型；实现可以包含必要的 code、stage 或 public_id 上下文，但 SHALL NOT 暴露原始异常。系统 SHALL NOT 暴露通用 callback HTTP 路由。

#### Scenario: Query achievements

- **WHEN** 已认证玩家请求 `GET /api/v1/achievement`
- **THEN** API SHALL 返回活动 Catalog 与历史 fallback 合并后的成就状态，不执行 condition 或 effect

#### Scenario: Explicit check is independent from Task

- **WHEN** 已认证玩家请求 `POST /api/v1/achievement/check`
- **THEN** AchievementCommandExecutor SHALL 执行 Check 后 Effect，不得执行 Task phase

#### Scenario: Claim an available active achievement

- **WHEN** 玩家对当前活动、available 且未删除的成就请求 claim
- **THEN** 系统 SHALL 在 Effect transaction 中执行 effect 并更新 claimed_at

#### Scenario: Claim is idempotent for an already claimed achievement

- **WHEN** 玩家重复 claim 已 claimed 成就
- **THEN** 系统 SHALL 保持 claimed 状态，不得重复执行 effect

#### Scenario: Replayed completed request does not rerun effects

- **WHEN** 玩家使用已完成的 Request-ID 重放 check 或 claim 请求
- **THEN** RequestCache SHALL 返回原始响应，不得再次执行 condition 或 effect
