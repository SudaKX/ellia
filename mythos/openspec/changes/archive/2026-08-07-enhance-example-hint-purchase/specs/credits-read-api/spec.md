## ADDED Requirements

### Requirement: API SHALL expose the authenticated player's VTB balance

系统 SHALL 提供 `GET /api/v1/credits`。请求必须通过 Bearer Token 认证；成功响应 SHALL 返回当前 VTB 数值和单调递增的余额版本，响应结构为：

```json
{
  "vtb": 5,
  "version": 0
}
```

#### Scenario: Authenticated player reads credits

- **WHEN** 玩家携带有效 Bearer Token 请求 `GET /api/v1/credits`
- **THEN** API SHALL 返回 200、当前 `vtb` 和当前 `version`

#### Scenario: Anonymous request is rejected

- **WHEN** 请求不携带有效 Bearer Token
- **THEN** API SHALL 拒绝请求并返回认证错误，不得返回任何玩家余额

### Requirement: Credits response SHALL reflect transactional balance changes

Credits API SHALL 从当前玩家的只读 CreditInterface 读取状态，不得执行发放、扣费或其他写入。玩家购买 Hint 后的下一次读取 SHALL 反映已提交的余额和版本变化。

#### Scenario: Balance reflects a committed Hint purchase

- **WHEN** 玩家成功购买一个价格为 2 VTB 的 Hint 后再次请求 Credits API
- **THEN** 返回的 `vtb` SHALL 比购买前少 2，`version` SHALL 比购买前增加

#### Scenario: Failed purchase does not change balance

- **WHEN** 玩家因余额不足购买 Hint 失败后请求 Credits API
- **THEN** 返回的 `vtb` 和 `version` SHALL 与失败前相同

### Requirement: Credits response SHALL prevent personalized cache reuse

Credits API 响应 SHALL 设置 `Cache-Control: no-store` 和 `Vary: Authorization`，确保不同玩家之间不复用余额响应。

#### Scenario: Balance response has private cache headers

- **WHEN** 已认证玩家成功请求 Credits API
- **THEN** 响应 SHALL 包含 `Cache-Control: no-store` 和包含 `Authorization` 的 `Vary` 头
