# 自定义 Credits 系统

## Why

当前 credits 系统只支持单一硬编码的 VTB 币种：`player_credits` 表只有一列 `vtb`，`CreditInterface` 只有 `grant_vtb`/`try_spend_vtb`，Hint 定价固定为 `vtb_cost`。谜题模块无法注册自己的代币类型，也无法为 Hint 使用 VTB 之外的定价。

## What Changes

- 新增 Credit 注册层：谜题模块通过 `registries.credits.register_template(CreditTemplate(...))` 注册自定义代币（沿用 Credit 命名），freeze 前由系统幂等注入内置 `vtb` 模板。
- **BREAKING** 数据迁移：`player_credits` 宽表废弃，VTB 全量迁入新长表 `player_credit_balances(player_id, credit_id, balance, version, updated_at)`；新增聚合状态表 `player_credit_states(player_id, version)`。迁移 downgrade 直接禁止（长表回填宽表必然丢失非 VTB 数据）。
- **BREAKING** `CreditInterface` 完全泛型化：删除 `PlayerCreditKind`、`vtb` 属性、`grant_vtb`、`try_spend_vtb`，替换为 `balance(credit_id)`、`grant(credit_id, n)`、`try_spend(credit_id, n)`、`balances`、`remove_unregistered(ids)`；保留 `CREDIT_VTB_ID = "vtb"` 常量。`credits.version` 改为聚合 state 行版本。
- **BREAKING** Hint 定价泛型化：删除 `Hint.vtb_cost` 与 `HintSummary.vtb_cost`，替换为注册项直接字段 `credit_id` + `credit_amount`；freeze 时校验 `credit_id` 已在 CreditCatalog 中注册；`disclose` 通过 `try_spend(hint.credit_id, hint.credit_amount)` 扣费。
- **BREAKING** `GET /api/v1/credits` 响应由 `{vtb, version}` 改为 `{credits: [{credit_id, balance}], version}`。
- 新增启动期 Credit reconciliation：仿 AccountReconciliationRunner，清理 catalog 中不存在的孤儿余额行，删除时同步 bump 聚合版本。
- `puzzles/example` 全部 VTB 调用点改写为泛型 `credit_id="vtb"` 调用点，并示范注册一个自定义 Credit。
- 7 个测试文件（33 处 VTB 型调用点）同步改写。

## Capabilities

### New Capabilities

- `custom-credit-registration`: Credit 模板注册、内置 vtb 注入、泛型余额接口、聚合状态版本、启动期 reconciliation 与孤儿行清理。
- `credit-priced-hints`: Hint 以 `credit_id` + `credit_amount` 定价、freeze 期跨 catalog 校验、按 credit 扣费的 disclose 流程与响应字段。

### Modified Capabilities

- `credits-read-api`: 响应结构从单币种 `{vtb, version}` 改为多币种 `{credits, version}`。
- `merged-file-tree-versioning`: credits 接口版本语义从 VTB 行版本改为覆盖全部 credit 余额变动的聚合状态版本。

## Impact

- 后端：`persistence/models/credits.py`、`players/interfaces/credits.py`、`players/loader.py`、`registry/bundle.py`、`registry/hints/`、`services/hints/service.py`、`services/credits/`（新增）、`endpoints/credits.py`、`endpoints/hints.py`、`core/config.py`（快照路径）、`main.py`（reconciliation 挂载）、`migrations/versions/0013`、`puzzles/example/__init__.py`
- 测试：`test_credits.py`、`test_example_module.py`、`test_example_vtb_task.py`、`test_player.py`、`test_hints.py`、`test_registry.py`、`test_tasks.py`
- 前端：desktop 消费 `/credits` 与 `/hints` 响应形状，需同步更新（本 change 仅覆盖后端）。
