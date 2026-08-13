## Why

Example 模块目前展示了认证、进度、Hint、VirtualAccount 和 Artifact，但没有展示 Task 系统如何根据玩家活动执行延迟奖励。新增一个 VTB allowance 任务，用惰性触发方式演示任务状态、`meta` 持久化、周期补发和额度上限。现在还需要让 Example 测试界面能够观察这套自动恢复状态，并提供显式处理控件，避免“读取页面”与“触发任务”之间的语义混淆。

## What Changes

- 在 Example 模块注册 `example.vtb-allowance` 异步 Task Handler，声明 `CREDITS` 依赖。
- 玩家 Construct 时激活该任务；任务不启动后台定时器，只在现有登录、已认证写操作、logout 和显式任务处理触发点运行。
- 首次有效触发时按当前剩余额度立即发放最多 5 点 VTB。
- 后续按 60 秒周期补发 VTB；一次请求可补算多个已过去的周期，但任务发放后的 VTB 不超过 10。
- 使用任务 `time_2` 保存下一次可发放时间，使用 JSON `meta` 保存 schema 版本、首次奖励状态、累计发放量和最近发放时间。
- 增加 Example Task 的单元、事务和 HTTP 测试，验证首次奖励、周期补发、延迟触发、上限和 `meta` 持久化。
- 更新 Example 模块和任务系统文档，说明惰性时间任务不会在玩家无请求时实时运行。
- 在 Example 测试界面展示 VTB 自动恢复状态，包括任务是否激活、下一次到期时间、可视倒计时、首次奖励状态、累计发放量和最近发放时间。
- 增加独立的主动处理控件，调用现有 `POST /api/v1/tasks/process` 后重新读取 Credits 与任务状态；保留顶部只读刷新控件的 GET 语义。
- 更新 Example 测试界面的手工验收说明，验证惰性恢复展示、主动处理、重复点击保护和错误反馈。

## Capabilities

### New Capabilities

- `example-vtb-task`: Example 模块中的 VTB 惰性奖励任务及其状态、周期和上限行为
- `example-vtb-task-console`: Example 测试界面对 VTB 惰性恢复状态的展示和主动处理交互

### Modified Capabilities

- 无

## Impact

- 修改 `src/mythos/puzzles/example/__init__.py`，接入 TaskRegistry 和 Construct 生命周期。
- 新增或更新 Example 任务测试、Example 领域文档、任务 API/系统说明和 `example/` 静态测试界面。
- 测试界面复用 `GET /api/v1/credits`、`GET /api/v1/tasks` 和 `POST /api/v1/tasks/process`；不新增 HTTP 路由、数据库表、后台调度器或外部依赖。
