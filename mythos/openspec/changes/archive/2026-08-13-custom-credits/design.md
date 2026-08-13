# 自定义 Credits 系统 — 设计文档

## Context

当前 credits 系统是单币种硬编码实现：

- `player_credits` 表只有 `vtb` 一列；`CreditInterface` 只有 `grant_vtb` / `try_spend_vtb`，`PlayerCreditKind` 枚举仅含 VTB。
- Hint 定价固定为 `vtb_cost`，`HintService.disclose` 硬调 `try_spend_vtb`。
- 文件树版本指纹（`pft4_`）依赖 `player.state_versions()`，其中 `credits.version` 直接读 VTB 行版本；参与条件由 access_rule 的 `module_handler(dependencies=...)` 声明并集决定（`merged_tree.py:_required_interfaces`）。
- 代码库已有成熟的可复用模式：accounts 的 `TemplateRegistry → Catalog → 每玩家状态表` 注册链路、`AccountReconciliationRunner` 的启动期快照对比清理、`PlayerVirtualAccountState` 的玩家级聚合状态行。

约束：AGENTS.md 规定谜题内容须在 Registry freeze 前注册；写入走调用方显式拥有的 transaction；模块不得新增 HTTP 路由。

## Goals / Non-Goals

**Goals:**

- 谜题模块可在 `register_all` 中注册自定义 Credit 类型（沿用 Credit 命名）。
- VTB 全量迁入长表，`player_credits` 宽表废弃，downgrade 禁止。
- `CreditInterface` 完全泛型化（`balance` / `grant` / `try_spend` / `remove_unregistered`），`puzzles/example` 所有调用点改写为泛型 `credit_id="vtb"` 形式。
- Hint 以 `credit_id` + `credit_amount` 直接字段定价，freeze 期跨 catalog 校验，disclose 按 credit 扣费。
- `credits.version` 变为覆盖全部余额变动的玩家级聚合状态版本，保证依赖 CREDITS 的 access_rule 缓存失效正确。
- 启动期 reconciliation 清理 catalog 之外的孤儿余额行。

**Non-Goals:**

- 桌面前端（desktop）同步改造（本 change 仅覆盖后端，响应形状变化在前端另行处理）。
- 泛化其它消费方（achievements 奖励、tasks 产出仍是谜题模块自己的回调逻辑，接口泛型化后自然可用，不改框架）。
- Credit 余额的负值、跨玩家转账、汇率/兑换机制。

## Decisions

### D1: 长表 `player_credit_balances` + 聚合状态行 `player_credit_states`

```
player_credit_balances                    player_credit_states
┌─────────────────────────────┐          ┌──────────────────────┐
│ player_id   PK, FK CASCADE  │          │ player_id   PK       │
│ credit_id   PK  String(128) │── 聚合 ──▶│ version  BigInteger  │
│ balance     CHECK >= 0      │          └──────────────────────┘
│ version     （行级审计）      │
│ updated_at                  │
└─────────────────────────────┘
```

- 替代方案 A：保留宽表、自定义 credit 加动态列 → SQLAlchemy 静态 ORM 无法由插件驱动加列，否决。
- 替代方案 B：`credits.version = sum(行级 version)` → reconciliation 删孤儿行使版本回退，破坏单调不变量，否决。
- 选聚合状态行：与 `PlayerVirtualAccountState` 同构；任何写路径（grant/try_spend/惰性建行/删行）同事务 bump +1；单调无回退；`state_versions` 协议（int >= 0）零改动。
- 行级 `version` 保留用于行内审计与未来乐观并发检测。

### D2: VTB 数据搬迁，downgrade 直接禁止

迁移 0013 顺序：建两表 → `INSERT ... SELECT player_id, 'vtb', vtb, version, updated_at FROM player_credits` → 用原 VTB 行版本初始化 state 行 → `DROP TABLE player_credits`。`downgrade()` 抛 `NotImplementedError`：长表回填宽表必然丢失非 VTB 数据，按决策禁止回滚。

### D3: 注册层复用 accounts 模式，内置 vtb 在 freeze 前注入

- `mythos/registry/credits/`：`definitions.py`（`CreditTemplate`，frozen dataclass，slug/JSON-safe 校验，`credit_template_version()` 指纹 `"ct1_"`）、`registry.py`（`CreditRegistry.register_template` / `freeze`）、`catalog.py`（`CreditCatalog`：`credit_ids`、`template`、snapshot、`template_version` 前缀 `"cc1_"`）、`versions.py`。
- `RegistryBundle.freeze()` 在 `credits.freeze()` 前幂等调用 `ensure_builtin_vtb()`（内部 `register_template` 跳过已存在的 `vtb` 模板或使用内置模板），保证 Catalog 永不为空——reconciliation 无需 `allow_empty_catalog`。
- `RuntimeCatalogs` 增加 `credits: CreditCatalog`；`PlayerLoader` 无需改构造签名（已持有 `catalogs`）。

### D4: CreditInterface 重写

- 构造注入 `CreditCatalog`；`load_credits` 一次 `SELECT` 全部余额行 + state 行 get-or-create（只读玩家零写入，仿 `load_accounts`）。
- `grant` / `try_spend`：
  - `credit_id` 必须 ∈ Catalog（防拼写错误产生孤儿行），金额校验沿用 `_validate_amount`。
  - 行已存在 → 沿用原子 `UPDATE ... RETURNING` 模式（原子 +1 行级版本与聚合状态版本）。
  - 行不存在 → 可写路径惰性创建 ORM 行（玩家行锁下无竞态，无需 `ON CONFLICT`，兼容 SQLite）。
- `balances` 只枚举 Catalog 内 credit；`remove_unregistered(ids)` 删行并 bump 聚合版本。
- 删除 `PlayerCreditKind`、`vtb` 属性、`grant_vtb`、`try_spend_vtb`；保留常量 `CREDIT_VTB_ID = "vtb"`。
- `version` 属性读 state 行。

### D5: Hint 定价直接字段 + freeze 跨校验

- `Hint`：删除 `vtb_cost`，新增 `credit_id: str`（slug 校验）、`credit_amount: int`（正整数校验）；`hint_version` 指纹把 `vtb_cost` 替换为这两个字段。
- `RegistryBundle.freeze()` 顺序：先 `credits.freeze()`，再 `hints.freeze(file_ids)`，随后遍历 `HintCatalog.hints` 校验每个 `credit_id` ∈ CreditCatalog，失败抛 `RegistryError`（与 `DuplicateStableIdError` 同风格，启动即失败）。
- `HintService`：`HintSummary` 扁平返回 `credit_id` / `credit_amount`；`disclose` 改调 `try_spend(hint.credit_id, hint.credit_amount)`；`endpoints/hints.py` 的 `INSUFFICIENT_CREDITS` 文案去掉 VTB 专指。
- `GET /api/v1/credits` 统一返回 `{"credits": [{"credit_id", "balance"}...], "version"}`，按 credit_id 排序，不再有顶层 `vtb` 字段。

### D6: 启动期 reconciliation 仿 AccountReconciliationRunner

- `services/credits/reconciliation.py`：`CreditReconciliationRunner`——catalog snapshot vs `TemplateSnapshotStore` 存储快照；`SELECT DISTINCT credit_id` 与 `catalog.credit_ids` 求差；stale 非空时按玩家 `load_writable(PlayerInterfaces.ALL)` 调 `remove_unregistered`；Catalog 变化时重写快照。
- `services/credits/snapshot.py` 提供 `CreditTemplateSnapshotStore`；`Settings` 增加 `credit_template_snapshot_path`。
- `main.py` lifespan 与其余三个 runner 并列挂载，保留 `allow_missing_tables`（test 环境）。

### D7: puzzles/example 泛型化

- 所有 `grant_vtb(x)` → `grant(CREDIT_VTB_ID, x)`；`credits.vtb` → `credits.balance(CREDIT_VTB_ID)`。
- 三个 Hint 改 `credit_id="vtb"` + `credit_amount`。
- 示范注册一个自定义 Credit（如 `example.moonstones`）并可将其用于示例（可选：新 Hint 定价或成就奖励），验证端到端链路。

## Risks / Trade-offs

- [迁移不可回滚，数据库损坏风险] → 迁移先在测试库与开发库验证数据搬迁 SQL；`downgrade` 抛错并附说明。
- [聚合状态行与余额行更新的原子性] → 同一 session/事务内完成；玩家行锁保证同玩家串行，不存在交错更新。
- [Hint 响应与 /credits 响应形状变化破坏前端] → 前后端同步发布；spec 明确新形状，桌面端改造单独跟进。
- [测试面大（7 文件 33 处调用点）] → tasks 中显式列出每个测试文件的改写与新增用例。
- [catalog 变化后遗留玩家余额的语义] → 按决策直接删除（reconciliation），删除即丢余额；如需保留语义，未来可改为"隐藏+恢复"，本期不做。
- [SQLite 与 Postgres 差异] → 惰性建行依赖玩家行锁而非 `ON CONFLICT`，避免方言分歧。

## Migration Plan

1. 先落代码与迁移 0013；对开发库执行 `alembic upgrade head` 验证 VTB 搬迁与 state 行初始化。
2. 部署顺序：后端先行（新端点形状），桌面端紧随其后切换 `/credits`、`/hints` 消费字段。
3. 回滚策略：迁移禁止 downgrade；回滚采用备份恢复而非降级。

## Open Questions

- 无。若未来需要保留被删除 credit 的玩家余额（而非 reconciliation 直接删除），另行提出 change。
