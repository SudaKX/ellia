## ADDED Requirements

### Requirement: Example 注册事件驱动的 Guest 登录成就

Example SHALL 注册活动成就 `example.guest-login`，其 `condition=None`、`immediate=True`，并具有声明 `PlayerInterfaces.CREDITS` 且授予 10 VTB 的异步 effect。Example SHALL 监听 `VirtualAccountLoggedInEvent`，且仅当事件账号 ID 为 `example.guest` 时调用玩家既有成就 grant interface。

#### Scenario: Guest 虚拟账号登录后立即达成并奖励成就

- **WHEN** 已认证的 Example 玩家成功登录虚拟账号 `example.guest`
- **THEN** `example.guest-login` SHALL 通过普通命令 transaction 达成，且其 immediate effect SHALL 通过既有 executor effect 流程授予 10 VTB

#### Scenario: 非 Guest 虚拟账号登录不授予 Guest 成就

- **WHEN** 已认证的 Example 玩家成功登录 `example.guest` 之外的虚拟账号
- **THEN** Example event listener SHALL NOT 授予 `example.guest-login`

#### Scenario: 重复 Guest 登录不重复奖励

- **WHEN** 已 earned 或 claimed `example.guest-login` 的玩家再次登录 `example.guest`
- **THEN** 玩家 SHALL NOT 从该成就收到额外奖励

### Requirement: Example 注册可领取的 VTB 阈值成就

Example SHALL 注册活动成就 `example.vtb-over-15`，其 condition 声明 `PlayerInterfaces.CREDITS`，并且仅在 `player.credits.vtb > 15` 时返回 true。该成就 SHALL 为非 immediate，其异步 claim effect SHALL 声明 `PlayerInterfaces.CREDITS` 并授予 10 VTB。

#### Scenario: VTB 阈值成就变为可领取

- **WHEN** 对 VTB 余额大于 15 的 Example 玩家运行普通成就条件检查
- **THEN** `example.vtb-over-15` SHALL 表示为已 earned、available 的成就，且不自动执行其 claim effect

#### Scenario: 领取 VTB 阈值成就后奖励玩家

- **WHEN** 玩家通过既有成就 claim command 领取 available 的 `example.vtb-over-15`
- **THEN** 其 claim effect SHALL 授予 10 VTB，且成就状态 SHALL 按既有成就契约变为 claimed

#### Scenario: 精确阈值余额不足以达成

- **WHEN** Example 玩家的 VTB 余额在成就条件检查时恰好为 15
- **THEN** `example.vtb-over-15` SHALL NOT 因该 condition 变为 available

### Requirement: Example 控制台展示并领取成就

认证后的 Example 控制台 SHALL 以既有 workspace 快照读取 `GET /api/v1/achievement`，并在既有“提示与 VTB”区域渲染每个返回成就的活动状态、immediate 状态、达成时间和领取时间。它 SHALL 仅为活动且 available 的成就提供 claim control。

#### Scenario: 认证后的 workspace 展示成就快照

- **WHEN** 已认证玩家加载或刷新 Example workspace
- **THEN** 控制台 SHALL 展示 `GET /api/v1/achievement` 返回的最新成就快照

#### Scenario: 玩家领取 available 成就

- **WHEN** 玩家操作活动且 available 成就的 claim control
- **THEN** 控制台 SHALL 使用新的 UUID `Request-ID` 发送既有 claim command，阻止该成就的并发重复操作，并在响应成功后刷新权威 Credits 和成就状态

#### Scenario: Claim warning 仍刷新状态

- **WHEN** 成就 claim 响应携带 warning followup 或 warning payload 但仍然成功
- **THEN** 控制台 SHALL 保留响应活动，并刷新权威成就快照，而不在本地假设 claim 结果

#### Scenario: 认证状态被清理

- **WHEN** 玩家登出或 session 失效
- **THEN** 控制台 SHALL 清理成就快照和 claim pending state，并不再展示 claim controls

### Requirement: Example 控制台展示命令 followup 活动

Example 控制台 SHALL 在独立于既有 HTTP 请求记录的活动集合中捕获成功命令 JSON 响应里的 `followups`。它 SHALL 渲染一个展示每项 followup action 和 data 的紧凑有上限列表，并在认证状态清理时清空列表。

#### Scenario: 成功命令产生 followup 活动

- **WHEN** 成功的 Example command response 包含一个或多个有效 followup
- **THEN** 控制台 SHALL 将它们追加到 followup 活动展示，且不改变 HTTP 请求记录

#### Scenario: Followup 活动有上限且具备防御性

- **WHEN** 命令产生超过控制台活动上限的 followup，或包含无法直接展示的 data
- **THEN** 控制台 SHALL 仅保留最近的有上限条目，并在不破坏 workspace UI 的情况下渲染 data

#### Scenario: 没有 followup 时不创建活动项

- **WHEN** 成功 command response 没有 followups 数组
- **THEN** 控制台 SHALL 保持既有 followup 活动不变

#### Scenario: 登出清空 followup 活动

- **WHEN** 玩家登出或 session 失效
- **THEN** 控制台 SHALL 移除全部已展示的 followup 活动
