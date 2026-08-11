# 成就 API

所有成就接口位于 `/api/v1/achievement`，需要 Bearer JWT。`check` 和 `claim` 是写命令，必须带 UUID `Request-ID`；同一个玩家重放已完成的 Request-ID 时，服务端返回原始缓存响应，不重新执行 condition 或 effect。

## 查询

```http
GET /api/v1/achievement
Authorization: Bearer <access token>
```

响应为：

```json
{
  "items": [
    {
      "public_id": "a1_...",
      "meta": {"title": "First step"},
      "immediate": false,
      "status": "locked"
    }
  ]
}
```

活动成就由当前冻结的 AchievementCatalog 提供。没有玩家状态时是 `locked`；有 earned 状态但没有 claimed 时间时是 `available`；有 claimed 时间时是 `claimed`。查询不会执行 condition、effect 或创建状态行。

## Check

```http
POST /api/v1/achievement/check
Authorization: Bearer <access token>
Request-ID: <UUID>
```

该接口不执行 Task。它在独立 Check transaction 中执行全部活动成就 condition，为新达成成就创建 earned 状态；Check 成功后在独立 Effect transaction 中执行 immediate effect。响应的 `content.check` 包含 `checked`、`earned` 和 `effects` public ID 数组。

## Claim

```http
POST /api/v1/achievement/claim/{public_id}
Authorization: Bearer <access token>
Request-ID: <UUID>
```

只有当前 Catalog 中已经达成且未领取的 active 成就可以领取，包含 immediate 成就的失败重试。effect 成功后写入 `claimed_at`；已领取成就再次领取时保持幂等且不重复执行 effect。无效、未达成或不可领取时返回 Problem Details；已删除成就即使存在历史状态也不能 claim。

## 删除与 fallback

玩家状态表只保存 `achievement_stable_id`、`earned_at`、`claimed_at` 和审计时间。puzzles 可以在 freeze 前通过 `AchievementRegistry.set_fallback(stable_id, meta, immediate)` 提供或覆盖展示数据，Catalog 以 freeze 时的最后数据为准，查询状态为 `deleted`。没有 fallback 时仍返回派生 public ID、历史状态和空 `meta`，状态为 `missing-fallback`；两者都不可 claim。fallback 没有 condition 或 effect，也没有 HTTP 修改接口。

## ID 与 warning

成就 public ID 不写入数据库，使用现有 file-ID signing key：

```text
a1_ + Base64URL(HMAC-SHA256(secret, "achievement:v1\0" + stable_id))
```

这是定位符，不是授权凭据；claim 仍检查当前玩家和状态。C/D 失败不会回滚已经提交的普通 Operation，成功响应中会增加安全 `warn`，例如 `achievement-check-failed` 或 `achievement-effect-failed`。原始异常只写服务端日志，不返回给客户端。
