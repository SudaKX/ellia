## Why

现有成就只能在 Operation 提交后的 condition 扫描中达成，无法表达虚拟账号登录等事件驱动、主动发放的成就。已完成的 EventBus 能在该事件所属的 Operation transaction 内执行模块 listener，但成就 Interface 缺少能安全落表并延后奖励的 `grant` 能力。

## What Changes

- 允许 Achievement definition 省略 condition；无 condition 成就只能由模块在可写 Player 上主动授予，不能由自动检查扫描达成。
- 为 AchievementInterface 增加只针对活动成就的幂等 `grant` 和当前 Operation 内的 `drain_grants`，主动授予立即写入 earned state，但不直接执行 effect。
- 普通 Endpoint Operation 在提交后合并 drained grants 与 condition Check 产生的 immediate effect 候选，以单个 Effect transaction 执行奖励和 claimed_at 更新。
- 主动 immediate grant 在已提交 Operation 后，即使 Check transaction 失败，仍 SHALL 尝试 Effect transaction；Effect 失败仍保留 earned state 并返回既有 warning。
- 保持 check、claim、Task-only command、Auth workflow 和 HTTP API 既有边界；本 change 不注册 Example 成就、不改 Example 界面。

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `achievement-system`: 支持 optional condition、模块主动 grant、grant drain 和合并后的 immediate effect 事务语义。
- `command-execution-boundaries`: 普通 Operation 在提交后收集主动 grants，并与 Achievement Check 结果合并执行单一 Effect batch。

## Impact

- 受影响区域包括 Achievement definition/registry/catalog、Player achievement interface/loader、AchievementService、EndpointCommandExecutor 及成就测试。
- 不新增数据库表、迁移、HTTP 路由、EventBus 事件类型、后台任务、消息队列或外部依赖。
- 后续 Example change 将监听既有 `VirtualAccountLoggedInEvent`，调用 `player.achievements.grant()` 并注册两个演示成就。
