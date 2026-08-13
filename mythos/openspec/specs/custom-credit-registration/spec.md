# Custom Credit Registration

## Purpose

定义谜题模块注册自定义 Credit 类型的能力：Credit 模板注册与冻结、内置 vtb 注入、泛型余额接口、聚合状态版本、长表持久化与启动期 reconciliation。

## Requirements

### Requirement: Puzzle modules SHALL register Credit templates before freeze

系统 SHALL 提供 `CreditRegistry.register_template`，谜题模块 SHALL 通过 `register_all(registries, *, environment)` 注册 `CreditTemplate`。`credit_id` SHALL 为小写 slug（`^[a-z0-9][a-z0-9._-]{0,127}$`），`display_name` SHALL 非空，`metadata` SHALL 为 JSON 可序列化对象。重复注册同一 `credit_id` SHALL 以 `DuplicateStableIdError` 失败；freeze 之后注册 SHALL 以 `RegistryFrozenError` 失败。每个模板 SHALL 提供由 `credit_id`、`display_name` 与 `metadata` 派生的稳定版本指纹。

#### Scenario: Module registers a custom credit

- **WHEN** 谜题模块在 `register_all` 中注册 `CreditTemplate("example.moonstones", "月石", metadata={"tier": "premium"})`
- **THEN** freeze 后的 CreditCatalog SHALL 包含该模板，且模板版本指纹随定义内容稳定变化

#### Scenario: Duplicate credit id is rejected

- **WHEN** 两个注册使用相同的 `credit_id`
- **THEN** Registry SHALL 抛出 `DuplicateStableIdError`，启动失败

#### Scenario: Registration after freeze is rejected

- **WHEN** 在 Catalog freeze 之后调用 `register_template`
- **THEN** Registry SHALL 抛出 `RegistryFrozenError`

### Requirement: The builtin vtb credit SHALL always be registered

系统 SHALL 在 Catalog freeze 前幂等注入内置 Credit 模板 `credit_id="vtb"`，无论谜题模块是否显式注册。CreditCatalog SHALL 永远至少包含 `vtb`，其稳定 ID SHALL 通过常量 `CREDIT_VTB_ID = "vtb"` 暴露。

#### Scenario: Catalog always contains vtb

- **WHEN** 谜题模块未注册任何 Credit 模板并完成 freeze
- **THEN** CreditCatalog SHALL 仍包含 `vtb` 模板

#### Scenario: Module cannot shadow the builtin vtb

- **WHEN** 谜题模块试图注册 `credit_id="vtb"` 的模板
- **THEN** 注册流程 SHALL 以与内置模板冲突处理，不产生重复条目

### Requirement: Player credit balances SHALL be stored per credit in a long table

系统 SHALL 以 `player_credit_balances` 表持久化余额，复合主键 `(player_id, credit_id)`，`balance` SHALL 为非负 `BigInteger`（CHECK `balance >= 0`），并携带行级 `version` 与 `updated_at`。迁移 SHALL 将原 `player_credits` 的 VTB 数据搬迁为该表 `credit_id="vtb"` 的行，并删除宽表；`downgrade` SHALL 直接禁止（抛错），不得回滚。

#### Scenario: VTB data migrates into the long table

- **WHEN** 对已有 `player_credits` 数据执行迁移
- **THEN** 每个玩家的 `vtb`、`version`、`updated_at` SHALL 成为 `player_credit_balances` 中 `credit_id="vtb"` 的行，且 `player_credits` 表被删除

#### Scenario: Downgrade is forbidden

- **WHEN** 尝试对包含自定义 Credit 数据的库执行迁移降级
- **THEN** 迁移 SHALL 抛出错误并拒绝执行

### Requirement: CreditInterface SHALL expose generic balance operations

`CreditInterface` SHALL 提供 `balance(credit_id)`、`grant(credit_id, amount)`、`try_spend(credit_id, amount)` 与 `balances` 枚举。所有操作 SHALL 只接受 Catalog 中已注册的 `credit_id`；金额 SHALL 为正整数；`try_spend` 在余额不足时 SHALL 抛出 `InsufficientCreditsError` 且不得修改状态。行级更新 SHALL 沿用原子 `UPDATE ... RETURNING` 模式并递增行级 `version`；首次访问未存在的行 SHALL 在可写路径中惰性创建。

#### Scenario: Grant increases a custom credit balance

- **WHEN** 可写玩家调用 `grant("example.moonstones", 3)`
- **THEN** 该 credit 余额 SHALL 增加 3，行级版本与聚合状态版本 SHALL 在同一事务中递增

#### Scenario: Spend fails without enough balance

- **WHEN** 玩家余额不足时调用 `try_spend(credit_id, amount)`
- **THEN** 接口 SHALL 抛出 `InsufficientCreditsError`，余额与版本 SHALL 保持不变

#### Scenario: Unknown credit id is rejected

- **WHEN** 调用 `grant`、`try_spend` 或 `balance` 时传入 Catalog 中不存在的 `credit_id`
- **THEN** 接口 SHALL 抛出错误，不得创建孤儿余额行

### Requirement: Credits interface version SHALL aggregate all credit balances

`credits.version` SHALL 来自玩家级聚合状态行 `player_credit_states(player_id, version)`。任何成功写入（grant、try_spend、惰性创建行、`remove_unregistered` 删除行）SHALL 在同一事务中把聚合版本递增 1。聚合版本 SHALL 单调不减，且任何可能影响 credit access_rule 结果的余额变动都 SHALL 使聚合版本变化。

#### Scenario: Any balance change bumps the aggregate version

- **WHEN** 任一 credit 的余额通过合法写入路径发生变化
- **THEN** `credits.version` SHALL 比写入前大，且与行级版本递增同属一个事务

#### Scenario: Removal of stale rows also bumps the version

- **WHEN** reconciliation 删除该玩家的孤儿余额行
- **THEN** 聚合状态版本 SHALL 递增，不得回退

### Requirement: Startup reconciliation SHALL remove stale credit balances

系统 SHALL 在启动期运行 Credit reconciliation：对比 CreditCatalog 快照与数据库中 `DISTINCT credit_id` 集合，对不属于 Catalog 的 credit_id，逐玩家加载可写玩家并调用 `CreditInterface.remove_unregistered(stale_ids)` 删除孤儿行。快照 SHALL 通过模板快照存储持久化，仅在 Catalog 变化后重写。内置 `vtb` SHALL 保证 Catalog 非空，reconciliation 不得因空 Catalog 拒绝启动。

#### Scenario: Stale credit rows are removed at startup

- **WHEN** 数据库中存在于当前 Catalog 中不存在的 credit_id 余额行
- **THEN** 启动 reconciliation SHALL 删除这些行并递增对应玩家的聚合状态版本

#### Scenario: Registered credits survive reconciliation

- **WHEN** 数据库中所有 credit_id 均属于当前 Catalog
- **THEN** reconciliation SHALL 不删除任何余额行，快照仅在 Catalog 定义变化时重写
