## MODIFIED Requirements

### Requirement: Achievement definitions are registered and frozen
系统 SHALL 提供独立的 `AchievementRegistry`。每个注册项 SHALL 包含唯一 `stable_id`、布尔 `immediate`、JSON 可序列化 `meta`、可选的同步 condition、异步 effect 和 Player Interface 依赖。Registry freeze 后 SHALL 拒绝新增或修改注册项，并生成只读 `AchievementCatalog`。condition 存在时 SHALL 是带依赖声明的同步单参数 callback；condition 为 null 时该成就 SHALL 只能通过主动 grant 达成。effect 对所有成就 SHALL 是带依赖声明的异步单参数 callback。

#### Scenario: Register a valid condition achievement
- **WHEN** puzzles 模块在 Registry freeze 前注册带合法 condition 和 effect 的 Achievement definition
- **THEN** AchievementCatalog SHALL 在 freeze 后提供该 stable ID 的 definition、condition/effect 依赖和版本指纹

#### Scenario: Register a valid grant-only achievement
- **WHEN** puzzles 模块在 Registry freeze 前注册 condition 为 null 且 effect 合法的 Achievement definition
- **THEN** Registry SHALL 接受定义，且 Catalog dependencies SHALL 包含 effect dependencies 而不包含不存在的 condition dependencies

#### Scenario: Reject invalid achievement callbacks
- **WHEN** 模块注册非同步 effect、非同步 condition、错误参数数量、缺少 effect 依赖声明或不可序列化 meta
- **THEN** Registry SHALL 拒绝注册并报告定义错误

#### Scenario: Reject registration after freeze
- **WHEN** 模块在 AchievementRegistry freeze 后尝试注册或替换 definition
- **THEN** Registry SHALL 拒绝修改

### Requirement: Achievement interface and service are transaction-neutral
系统 SHALL 提供 `PlayerInterfaces.ACHIEVEMENTS`、`Player.achievements` 和 PlayerLoader 加载入口。AchievementInterface SHALL 只管理当前 Player 的状态记录和当前已加载聚合内的主动 grant 候选。AchievementService SHALL 使用调用方提供的 Session 和 Player，不得提交、回滚、创建 HTTP 响应或管理 Request-ID。

#### Scenario: Load achievement state with a writable Player
- **WHEN** CommandExecutor 加载 writable Player 的 Achievement Interface
- **THEN** Interface SHALL 读取该玩家的状态记录，并允许调用方 transaction 管理后续写入

#### Scenario: Service participates in caller transaction
- **WHEN** AchievementService 创建 earned record 或更新 claimed_at
- **THEN** 修改 SHALL 随调用方 transaction 一起提交或回滚

#### Scenario: Grant an active achievement in an operation
- **WHEN** 模块在 writable Player 的 Operation transaction 内调用 `player.achievements.grant(stable_id)`，且 stable_id 属于当前活动 Catalog
- **THEN** Interface SHALL 幂等创建或读取 earned state，并将 stable_id 缓存在当前聚合的 pending grant 候选中，不得直接执行 effect、更新 claimed_at 或提交 transaction

#### Scenario: Reject a grant for a non-active achievement
- **WHEN** 模块主动 grant 未知、fallback 或当前已删除 achievement stable ID
- **THEN** Interface SHALL 拒绝该调用，且不得创建或修改 PlayerAchievementState

#### Scenario: Drain grants once per loaded operation aggregate
- **WHEN** 调用方在同一 Operation aggregate 上调用 `drain_grants()`
- **THEN** Interface SHALL 返回并清空 pending grant stable IDs，且不得执行 effect、提交 transaction 或修改 claimed_at

### Requirement: Achievement checks run after committed operations
普通写命令 SHALL 在 Operation transaction 提交后执行独立的 Check transaction。Check SHALL 读取当前 Player 状态，仅执行带 condition 的活动成就，并为新达成成就创建 earned record。condition 返回 false SHALL NOT 被视为错误；condition 为 null 的成就 SHALL 不得由 Check 达成。

#### Scenario: Operation success triggers a check
- **WHEN** 普通写命令的 Operation transaction 成功提交
- **THEN** CommandExecutor SHALL 启动独立 Check transaction 并执行带 condition 的 Achievement condition

#### Scenario: Condition creates an earned state once
- **WHEN** condition 返回 true 且玩家尚无该成就状态
- **THEN** Check transaction SHALL 创建 earned record；重复检查 SHALL 保持幂等

#### Scenario: Grant-only achievement is ignored by checks
- **WHEN** 当前活动成就的 condition 为 null
- **THEN** `POST /achievement/check` 和普通 Operation 的 Check transaction SHALL 不得为该成就创建 earned state或执行其 effect

#### Scenario: Condition failure rolls back the check
- **WHEN** condition、状态写入或 Check hook 抛出异常
- **THEN** Check transaction SHALL 整体回滚，向最终响应增加 warn，并保持已提交 Operation 不变；已从 Operation drain 的主动 immediate grants SHALL 仍可进入独立 Effect transaction

### Requirement: Immediate effects and claims run in independent effect transactions
普通 Operation 的 Check 成功后，系统 SHALL 在独立 Effect transaction 中执行本轮 immediate effect，并更新相应领取状态。普通 Operation SHALL 将其已提交 Operation 内 drained 的主动 grants 与 Check 产生的 immediate candidates 合并、按当前 Catalog 稳定顺序去重，并至多启动一个 Effect transaction。Effect SHALL 以单个 batch transaction 执行，不使用 per-effect savepoint。Effect 失败 SHALL 回滚整个 Effect transaction，但 SHALL 保留已提交的 earned record。

#### Scenario: Immediate achievement effect succeeds
- **WHEN** 新达成或主动 grant 的成就 immediate 为 true 且 effect 成功
- **THEN** Effect transaction SHALL 提交 effect 修改和 claimed_at，并返回无 warn 的结果

#### Scenario: Proactive immediate grant survives a failed check
- **WHEN** Operation transaction 已提交一个主动 immediate grant，随后 Check transaction 失败
- **THEN** CommandExecutor SHALL 返回 achievement-check-failed warning，并 SHALL 在独立 Effect transaction 中尝试该主动 grant 的 effect

#### Scenario: One effect failure rolls back the effect batch
- **WHEN** 任一合并 candidate 的 effect 或 Effect hook 抛出异常
- **THEN** 整个 Effect transaction SHALL 回滚，后续 effect SHALL NOT 执行，earned record SHALL 保留，最终响应 SHALL 包含 warn

#### Scenario: Non-immediate proactive grant remains claimable
- **WHEN** 模块主动 grant immediate 为 false 的活动成就
- **THEN** Operation 后的 Effect transaction SHALL 不得执行其 effect，状态 SHALL 保持 available 并可通过既有 claim API 领取

#### Scenario: Repeated grant does not duplicate a claimed reward
- **WHEN** 模块对已经 claimed 的活动成就重复主动 grant
- **THEN** 系统 SHALL 不得再次执行 effect 或修改 claimed_at
