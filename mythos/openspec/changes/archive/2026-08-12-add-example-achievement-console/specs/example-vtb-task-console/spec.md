## ADDED Requirements

### Requirement: Example workspace 快照包含成就

Example 测试控制台 SHALL 与认证后的 workspace 读取一起加载既有 `GET /api/v1/achievement` 快照。它 SHALL 在认证清理时清除该快照，同时保持既有 VTB 恢复加载和显式处理行为。

#### Scenario: Workspace 刷新包含成就状态且不处理任务

- **WHEN** 已认证玩家操作既有通用刷新控件
- **THEN** 控制台 SHALL 将最新成就快照与既有只读 workspace 数据一起加载，且 SHALL NOT 调用 `POST /api/v1/tasks/process`

#### Scenario: Guest 登录刷新成就状态

- **WHEN** 已认证玩家成功登录 Example 虚拟账号
- **THEN** 控制台 SHALL 将 Credits 和成就状态作为既有强制 workspace 刷新的一部分重新加载

#### Scenario: 清理认证会移除成就状态

- **WHEN** 玩家登出或 session 失效
- **THEN** 控制台 SHALL 将成就快照与既有 VTB 恢复状态及其他 workspace 数据一起清理
