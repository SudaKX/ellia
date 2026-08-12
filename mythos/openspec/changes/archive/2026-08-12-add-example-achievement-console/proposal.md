## 原因

主动 grant 和 EventBus 已具备框架能力，但 Example 模块与开发页面尚未展示事件驱动成就、条件成就及其领取流程。Example 页面也会接收命令响应的 `followups`，却没有可见位置展示这些领域通知，无法作为完整命令流程的演示工具。

## 变更内容

- 在 Example 注册一个 Guest 虚拟账号登录时主动授予、立即发放 10 VTB 的成就，以及一个 VTB 大于 15 时达成、领取后发放 10 VTB 的非立即成就。
- 使用 `VirtualAccountLoggedInEvent` listener 主动 grant Guest 成就，且保持模块不拥有 Session、transaction 或 HTTP 路由。
- 扩展 `/example/` workspace：认证后读取 `GET /achievement`，展示活动/历史成就状态、时间和 immediate 标记，并允许领取 active available 成就。
- 在 Example 页面增加紧凑的 followup 活动展示，捕获普通命令成功响应中的 `followups`，展示 action 和 data，认证清理时同步清空。
- 更新 Example 端到端测试、页面手工验收与模块/API flow 文档。

## 能力范围

### 新增能力

- `example-achievement-console`: Example 成就注册、事件驱动奖励、条件奖励、成就领取界面和命令 followup 展示。

### 修改能力

- `example-vtb-task-console`: Example workspace 的认证状态加载与清理扩展为包含 achievement snapshot，且保持原 recovery 工作流不变。

## 影响范围

- 受影响区域包括 `puzzles/example`、Example 静态 HTML/CSS/JS、Example 集成测试、模块/API 文档和 OpenSpec specs。
- 使用既有 Achievement API、Credits Interface、EventBus 和 Request-ID，不新增数据库表、HTTP 路由、Service、后台调度或前端依赖。
