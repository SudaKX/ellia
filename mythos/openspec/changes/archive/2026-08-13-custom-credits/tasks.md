# 实施任务

## 1. 数据层

- [x] 1.1 重写 `mythos/persistence/models/credits.py`：`PlayerCreditBalance`（`player_credit_balances`，PK `(player_id, credit_id)`，`balance` CHECK >= 0、`version`、`updated_at`）与 `PlayerCreditState`（`player_credit_states`，PK `player_id`，`version`）；常量 `CREDIT_VTB_ID = "vtb"`
- [x] 1.2 新增迁移 `migrations/versions/0013_custom_credits.py`：建两表、`INSERT ... SELECT player_id, 'vtb', vtb, version, updated_at FROM player_credits` 搬迁、初始化 state 行、`DROP TABLE player_credits`；`downgrade()` 抛 `NotImplementedError`
- [x] 1.3 对开发库执行 `alembic upgrade head` 验证搬迁数据正确

## 2. 注册层

- [x] 2.1 新增 `mythos/registry/credits/definitions.py`：`CreditTemplate`（slug/display_name/JSON-safe 校验）+ `credit_template_version()` 指纹 `"ct1_"`
- [x] 2.2 新增 `mythos/registry/credits/registry.py`：`CreditRegistry.register_template` / `freeze`（重复注册 `DuplicateStableIdError`、冻结后 `RegistryFrozenError`）
- [x] 2.3 新增 `mythos/registry/credits/catalog.py` + `versions.py` + `__init__.py`：`CreditCatalog`（`credit_ids`、`template`、snapshot、`template_version` 前缀 `"cc1_"`）
- [x] 2.4 `RegistryBundle` 挂载 `credits = CreditRegistry()`；`freeze()` 先幂等注入内置 `vtb` 模板再 freeze credits；`RuntimeCatalogs` 增加 `credits: CreditCatalog`

## 3. 玩家接口与加载

- [x] 3.1 重写 `mythos/players/interfaces/credits.py`：删除 `PlayerCreditKind`、`vtb`、`grant_vtb`、`try_spend_vtb`；新增 `balance(credit_id)`、`grant(credit_id, amount)`、`try_spend(credit_id, amount)`、`balances`、`remove_unregistered(ids)`、`version`（读 state 行）；credit_id ∈ Catalog 校验；行级 UPDATE..RETURNING 原子模式 + 惰性建行；每次写 bump 聚合状态版本
- [x] 3.2 `mythos/players/loader.py` 的 `load_credits` 改为一次 SELECT 全部余额行 + state 行 get-or-create，注入 `self._catalogs.credits`
- [x] 3.3 更新 `players/interfaces/__init__.py` 导出（移除 `PlayerCreditKind` 导出）

## 4. Hint 定价泛型化

- [x] 4.1 `mythos/registry/hints/definitions.py`：`Hint` 删 `vtb_cost`，增 `credit_id` + `credit_amount`（校验）；`hint_version` 指纹字段更新
- [x] 4.2 `RegistryBundle.freeze()` 在 hints freeze 后跨校验每个 hint 的 `credit_id` ∈ CreditCatalog，否则 `RegistryError`
- [x] 4.3 `mythos/services/hints/service.py`：`HintSummary` 改 `credit_id`/`credit_amount` 字段与 `body()`；`disclose` 改调 `try_spend(hint.credit_id, hint.credit_amount)`
- [x] 4.4 `mythos/endpoints/hints.py`：`INSUFFICIENT_CREDITS` 文案去 VTB 专指

## 5. 端点与 reconciliation

- [x] 5.1 `mythos/endpoints/credits.py`：响应改为 `{"credits": [{"credit_id", "balance"}...], "version"}`，按 credit_id 排序
- [x] 5.2 新增 `mythos/services/credits/`：`reconciliation.py`（`CreditReconciliationRunner` 仿 `AccountReconciliationRunner`，含 stale 清理与快照重写）与 `snapshot.py`（`CreditTemplateSnapshotStore`）
- [x] 5.3 `core/config.py` 增加 `credit_template_snapshot_path` 配置及 `credit_snapshot_path` 属性
- [x] 5.4 `main.py` lifespan 挂载 `CreditReconciliationRunner`（`allow_missing_tables` 依 environment）

## 6. 示例模块与调用点

- [x] 6.1 `puzzles/example/__init__.py`：三个 Hint 改 `credit_id="vtb"` + `credit_amount`；`grant_vtb`/`credits.vtb` 调用点全部改泛型 `grant(CREDIT_VTB_ID, ...)` / `balance(CREDIT_VTB_ID)`
- [x] 6.2 在 example 模块注册一个自定义 Credit（如 `example.moonstones`）并接入示例流程（新 Hint 定价或成就奖励），验证端到端

## 7. 测试

- [x] 7.1 更新 `tests/test_credits.py`：端点新响应形状
- [x] 7.2 更新 `tests/test_hints.py`：`credit_id`/`credit_amount` 注册与扣费断言
- [x] 7.3 更新 `tests/test_registry.py`：Hint 注册项新字段
- [x] 7.4 更新 `tests/test_player.py`、`tests/test_tasks.py`、`tests/test_example_module.py`、`tests/test_example_vtb_task.py`：全部 VTB 型调用点改泛型
- [x] 7.5 新增：迁移搬迁与 downgrade 禁止、聚合状态版本单调性、自定义 credit 发放/扣费、freeze 跨 catalog 校验失败、reconciliation 孤儿行清理测试
- [x] 7.6 全量跑 `pytest tests`（含 `-k` 聚焦用例），确认 RustFS 集成外全部通过

## 8. 文档

- [x] 8.1 更新 `openspec/specs/` 主 spec（apply 后归档 delta）；如 AGENTS.md 或 README 提及 credits API 形状则同步更新
