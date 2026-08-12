# Example VTB 任务控制台

## Purpose

定义 Example 测试控制台对 VTB recovery 任务状态的展示、倒计时、显式处理、成就快照加载和认证状态清理行为。

## Requirements

### Requirement: Example 控制台展示惰性 VTB recovery 状态

Example 测试控制台 SHALL 在玩家已认证时加载既有 `GET /api/v1/tasks` 快照及 Credits 数据，并展示 `example.vtb-allowance` 任务状态。该展示 SHALL 包含当前 VTB 余额、任务状态、来自 `time_2` 的下次到期时间、存在到期时间时的客户端倒计时，以及持久化 `meta` 字段 `initial_grant_applied`、`total_granted` 和 `last_granted_at`。

#### Scenario: 认证控制台展示 recovery 状态

- **WHEN** 已认证玩家加载或读取 Example workspace
- **THEN** 控制台 SHALL 展示当前 VTB 余额和最新的 `example.vtb-allowance` 快照，包括其下次到期时间和持久化授予元数据

#### Scenario: 控制台说明惰性执行

- **WHEN** 下次到期时间已到，但玩家未触发任务
- **THEN** 控制台 SHALL 指示任务已就绪或到期，但 SHALL NOT 自动调用 `POST /api/v1/tasks/process`，也不得声称 VTB 已被授予

#### Scenario: 缺失任务状态可见

- **WHEN** 已认证任务快照不含 `example.vtb-allowance`，或其首次处理元数据不完整
- **THEN** 控制台 SHALL 展示明确的未初始化状态，而非推断授予成功

### Requirement: Example 控制台提供显式 VTB 任务处理

Example 测试控制台 SHALL 提供用于处理当前任务状态的独立主动控件。该控件 SHALL 在每次操作时使用新的 UUID `Request-ID` 调用既有 `POST /api/v1/tasks/process` endpoint，在请求 pending 时阻止并发重复操作，并在响应成功后重新加载权威 Credits 和任务状态。

#### Scenario: 玩家主动处理 allowance

- **WHEN** 已认证玩家操作 VTB recovery 控件
- **THEN** 控制台 SHALL 在 pending 时禁用控件，展示任务报告，并从服务器刷新展示的 VTB 余额和任务元数据

#### Scenario: 只读刷新不处理任务

- **WHEN** 玩家操作既有通用刷新控件
- **THEN** 控制台 SHALL 仅执行既有读取操作，且 SHALL NOT 调用 `POST /api/v1/tasks/process`

#### Scenario: 处理失败

- **WHEN** 显式任务请求返回错误或无法连接服务器
- **THEN** 控制台 SHALL 保留最后已知的任务和 VTB 状态，展示用户可读错误，并重新启用主动控件

#### Scenario: 认证被清理

- **WHEN** 玩家登出或 session 失效
- **THEN** 控制台 SHALL 清理 VTB 任务快照、倒计时、处理状态和 recovery 消息

### Requirement: Example workspace 快照包含成就

Example 测试控制台 SHALL 与认证后的 workspace 既有读取并行加载 `GET /api/v1/achievement` 快照。它 SHALL 在认证清理时清除该快照，同时保持既有 VTB recovery 加载和显式处理行为。

#### Scenario: Workspace 刷新包含成就状态且不处理任务

- **WHEN** 已认证玩家操作既有通用刷新控件
- **THEN** 控制台 SHALL 将最新成就快照与既有只读 workspace 数据并行加载，且 SHALL NOT 调用 `POST /api/v1/tasks/process`

#### Scenario: Guest 登录刷新成就状态

- **WHEN** 已认证玩家成功登录 Example 虚拟账号
- **THEN** 控制台 SHALL 将 Credits 和成就状态作为既有强制 workspace 刷新的一部分重新加载

#### Scenario: 清理认证会移除成就状态

- **WHEN** 玩家登出或 session 失效
- **THEN** 控制台 SHALL 将成就快照与既有 VTB recovery 状态及其他 workspace 数据一起清理
