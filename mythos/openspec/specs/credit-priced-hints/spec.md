# Credit Priced Hints

## Purpose

定义 Hint 以 `credit_id` + `credit_amount` 定价的行为：注册项字段、freeze 期跨 catalog 校验、disclose 扣费与响应字段。

## Requirements

### Requirement: Hint registration SHALL carry credit price fields

`Hint` SHALL 以 `credit_id: str` 与 `credit_amount: int` 两个直接字段定价，取代 `vtb_cost`。`credit_id` SHALL 为小写 slug（`^[a-z0-9][a-z0-9._-]{0,127}$`），`credit_amount` SHALL 为正整数。`hint_version` 指纹 SHALL 包含 `credit_id` 与 `credit_amount`。

#### Scenario: Register a hint priced in a custom credit

- **WHEN** 谜题模块注册 `Hint(..., credit_id="example.moonstones", credit_amount=5)`
- **THEN** 注册 SHALL 成功，且 hint 版本随 `credit_id` 或 `credit_amount` 变化

#### Scenario: Invalid price fields are rejected

- **WHEN** `credit_id` 不符合 slug 格式或 `credit_amount` 非正整数
- **THEN** Registry SHALL 拒绝注册并抛出错误

### Requirement: Freeze SHALL validate hint credit references

系统 SHALL 在 Registry freeze 阶段校验每个 Hint 的 `credit_id` 已在 CreditCatalog 中注册（含内置 `vtb`）。任何引用未注册 credit 的 Hint SHALL 使 freeze 失败，应用不得启动。

#### Scenario: Hint references an unregistered credit

- **WHEN** Hint 的 `credit_id` 不在 CreditCatalog 中且 freeze 执行
- **THEN** freeze SHALL 抛出 RegistryError 并中止启动

#### Scenario: Hint references the builtin vtb

- **WHEN** Hint 以 `credit_id="vtb"` 定价且 freeze 执行
- **THEN** freeze SHALL 成功

### Requirement: Disclose SHALL spend the priced credit

`HintService.disclose` SHALL 在新 claim 成立时调用 `player.credits.try_spend(hint.credit_id, hint.credit_amount)`；余额不足 SHALL 以 `409 insufficient-credits` 问题响应结束，disclosure 状态与余额 SHALL 保持不变。已披露的 Hint 再次请求 SHALL 保持幂等，不重复扣费。

#### Scenario: Disclose spends the custom credit

- **WHEN** 玩家以足够的 `example.moonstones` 余额首次披露定价为月石的 Hint
- **THEN** 该 credit 余额 SHALL 减少 `credit_amount`，Hint SHALL 标记为已披露

#### Scenario: Insufficient custom credit blocks disclosure

- **WHEN** 玩家对应 credit 余额不足
- **THEN** API SHALL 返回 `409 insufficient-credits`，disclosure 与余额 SHALL 不变

#### Scenario: Repeated disclose does not charge twice

- **WHEN** 玩家再次披露已披露的 Hint
- **THEN** 流程 SHALL 成功且不产生新的扣费

### Requirement: Hint responses SHALL expose credit price fields

Hint 摘要响应 SHALL 以 `credit_id` 与 `credit_amount` 字段返回价格，取代 `vtb_cost`。

#### Scenario: Hint listing exposes credit price

- **WHEN** 玩家请求 `GET /api/v1/hints`
- **THEN** 每个 Hint 的响应体 SHALL 包含 `credit_id` 与 `credit_amount`，且不得包含 `vtb_cost`
