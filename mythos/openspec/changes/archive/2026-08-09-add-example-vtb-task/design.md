## Context

Example 模块已经注册进度、Hint、VirtualAccount、Artifact、脚本和 validation，并在 Construct 时发放可配置的初始 VTB。通用 Task 系统已经提供 TaskRegistry、`Player.tasks`、TaskContext、惰性触发点、任务事务和 `meta` 持久化能力；本变更只增加一个 Example 领域任务，用于演示这些能力。

任务不会拥有独立调度器。玩家只有在登录、已认证写操作、logout 或显式任务处理请求中产生请求时，TaskExecutor 才会调用 Handler。玩家没有请求时，数据库不会被后台进程修改。

## Goals / Non-Goals

**Goals:**

- 在 Example Registry 中注册稳定任务身份 `example.vtb-allowance`。
- 玩家 Construct 时为该玩家激活任务，并让首次有效任务处理立即发放最多 5 点 VTB。
- 以 60 秒为一个周期，根据两次请求之间经过的周期数补发 VTB。
- 使任务发放后的玩家 VTB 不超过 10。
- 使用 `time_2` 保存下一次到期时间，并使用严格 JSON `meta` 保存可观察的任务私有状态。
- 通过现有 Task transaction、Credits Interface 和 HTTP 测试验证行为。

**Non-Goals:**

- 不启动后台 asyncio 定时器、Celery、Worker 或跨玩家批处理。
- 不修改全局 `CreditInterface.grant_vtb()` 的系统级上限语义；上限只约束该 Example 任务发放的结果。
- 不新增任务 HTTP 路由、数据库表或外部依赖。
- 不为历史玩家批量创建任务；玩家在下一次 Construct 或显式业务激活时获得任务。

## Decisions

### 1. 在 Example 注册 Task Handler 和 Construct 激活

在 `example.register()` 中使用 `registries.tasks.task()` 注册 `example.vtb-allowance`，依赖声明为 `PlayerInterfaces.CREDITS`。同一 `register()` 调用中增加 Construct lifecycle Handler，调用 `context.player.tasks.add_task()`；使用晚优先级，使现有 Example Construct 初始化先完成。

任务注册身份属于 Example Catalog，玩家任务行只保存通用运行状态。重复 Construct 或重复激活保持 `add_task()` 幂等，不重置既有 `time_1`、`time_2` 或 `meta`。

### 2. 使用 time_2 保存下一次到期时间

`time_1` 保留 TaskExecutor 的通用语义，由执行器在 Handler 正常返回时写入成功时间。Example 将 `time_2` 解释为 `next_due_at`：

- 首次 Handler 处理时，若 `meta.initial_grant_applied` 不为真且 VTB 尚未达到上限，发放 `min(5, 10 - current_vtb)`，设置 `time_2 = now + 60s`，并正常返回。
- 若首次处理时 VTB 已达到上限，设置下一次检查时间并调用 `defer()`，不标记首次奖励已完成。
- 后续 Handler 在 `now < time_2` 时调用 `defer()`，保留旧 `time_1`。
- 到期后计算包含当前到期点在内的已到期周期数，一次最多发放该数量的 VTB；发放量还受 `10 - current_vtb` 限制。
- 发放后推进 `time_2`；若已达到 10 点，则将下一次检查安排在 `now + 60s`，避免保留无限过去的欠账。

### 3. 使用 meta 记录 Example 私有状态

任务 meta 使用版本化对象：

```json
{
  "schema_version": 1,
  "initial_grant_applied": true,
  "total_granted": 5,
  "last_granted_at": "2026-08-09T12:00:00+00:00"
}
```

`total_granted` 记录该任务累计发放量，`last_granted_at` 用于诊断，`initial_grant_applied` 防止首次 5 点奖励重复发放。当前 VTB 始终从 `Player.credits` 读取，不能仅依赖 meta 判断上限。未知或缺失字段按未初始化处理；版本升级由未来显式迁移任务负责。

### 4. 补发规则和并发边界

设 `due_at = time_2`，当 `now >= due_at` 时：

```text
due_periods = floor((now - due_at) / 60 seconds) + 1
available = max(0, 10 - current_vtb)
grant = min(due_periods, available)
```

`grant > 0` 时通过 `Player.credits.grant_vtb(grant)` 写入，并在同一 Task transaction 中更新 meta 和 `time_2`。TaskExecutor 的玩家行锁保证同一玩家的并发任务阶段串行化；其他业务仍可在后续请求中按当前 VTB重新计算剩余额度。

### 5. 测试时间和公开行为

测试不等待真实 60 秒。Example Task 测试使用可控的 TaskExecutor 当前时间，或替换现有 UTC 时钟函数，验证首次奖励、未到期 defer、周期补发、长时间补算、上限和 meta JSON。HTTP 测试复用现有 `/api/v1/tasks` 与 `/api/v1/tasks/process`，不添加 Example 专属路由。

### 6. Example 测试界面的状态展示与主动处理

Example 静态测试界面在已有 workspace 加载流程中并行读取 `GET /api/v1/tasks`，从任务列表中选择 `example.vtb-allowance`，与现有 Credits 余额一起提交给渲染层。界面展示以下只读信息：

- 当前 VTB 与任务上限 10；
- 任务状态（未激活、等待首次处理、等待下一个周期、已到期可处理或当前已达上限）；
- `time_2` 的下一次到期时间和基于客户端当前时间计算的可视倒计时；
- `meta.initial_grant_applied`、`meta.total_granted` 和 `meta.last_granted_at`。

倒计时只负责让用户知道何时可以再次处理，不会在到期时自动发送请求，也不改变后端的惰性任务语义。任务缺失、`time_2` 缺失或 meta 字段缺失时显示明确的待初始化状态，而不是猜测奖励已经发放。

界面增加独立的“立即处理”控件，调用：

```text
POST /api/v1/tasks/process
Request-ID: <new UUID per click>
```

控件请求期间禁用，成功后使用响应中的任务报告显示本轮结果，并重新执行 Credits、Tasks 及其他 workspace 读取；失败时保留当前状态并展示 Problem Details 的用户可读错误。已有顶部“刷新”控件继续只执行 GET，不调用任务处理端点。这样用户可以明确区分“查看当前状态”和“主动触发一次惰性恢复”。

浏览器端不引入新的定时任务或轮询器；倒计时可由单个短生命周期显示计时器驱动，离开认证 workspace 或注销时销毁。所有状态更新仍以服务器返回的 Credits 和 Task snapshot 为准。

## Risks / Trade-offs

- [风险] 任务只在请求时运行，玩家离线期间不会实时收到 VTB。→ API 和 Example 文档明确说明惰性语义；下一次触发时按经过周期补算。
- [风险] 其他业务来源仍可能把 VTB 增加到 10 以上。→ 本变更只保证 Example 任务自己的发放不超过 10；全局上限需要另行设计。
- [风险] 玩家长时间离线后一次补发多个周期，可能产生瞬时较大的 VTB 变化。→ 单次发放仍限制为当前剩余额度，并在达到 10 后停止补账。
- [风险] Handler 代码或 meta schema 变更可能影响已有任务行。→ 保存 `schema_version`，破坏性变化通过新任务身份或显式迁移处理。

## Migration Plan

1. 发布包含 Example Task 注册和 Handler 的应用版本。
2. 新玩家在 Construct 时创建 `example.vtb-allowance` 任务；现有玩家不做批量回填。
3. 通过登录、写命令或 `POST /api/v1/tasks/process` 触发首次奖励和周期补算。
4. 回滚时停止 Example Task 注册和激活逻辑；由于通用任务 reconciliation 会清理不再注册的身份，需先评估是否保留玩家任务状态。

## Open Questions

无。首次奖励采用最多 5 点，周期奖励采用按已到期周期数补算且总额不超过 10 点；界面主动处理复用固定任务 API，顶部刷新保持只读。
