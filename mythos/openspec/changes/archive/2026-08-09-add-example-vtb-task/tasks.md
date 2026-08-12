## 1. Example Task 注册与激活

- [x] 1.1 在 Example 模块增加 `example.vtb-allowance`、60 秒周期、首次 5 点和 VTB 上限 10 的常量，并导入 `TaskContext` 与生命周期优先级。
- [x] 1.2 在 `register()` 中使用 `registries.tasks.task()` 注册异步 Handler，声明 `PlayerInterfaces.CREDITS` 依赖。
- [x] 1.3 增加晚优先级 Construct Handler，通过 `context.player.tasks.add_task()` 激活任务，并验证重复激活不重置状态。

## 2. VTB Handler 状态算法

- [x] 2.1 实现首次执行逻辑：按当前 VTB 计算最多 5 点的安全发放量，成功后更新 `meta`、`time_2` 和累计发放状态。
- [x] 2.2 实现未到期 `defer()` 逻辑，保证 `time_1` 保持不变且不修改 VTB。
- [x] 2.3 实现到期周期计算、多个周期补发和达到 10 点后的停止/延迟检查逻辑。
- [x] 2.4 处理缺失或旧版本 meta，保持 JSON 可序列化，并确保当前 `Player.credits.vtb` 是上限判断的唯一事实来源。

## 3. 测试与时间控制

- [x] 3.1 增加可控 UTC 时间测试工具或 TaskExecutor 时钟替换方案，避免测试真实等待 60 秒。
- [x] 3.2 测试 Example Construct 激活任务、重复激活幂等和首次发放最多 5 点。
- [x] 3.3 测试 `meta` 的 schema 版本、首次奖励标志、累计发放量和最近发放时间持久化。
- [x] 3.4 测试未到期 defer、单周期发放、多个周期补算和时间推进。
- [x] 3.5 测试当前 VTB 为 8/9/10 时的上限行为，以及达到上限后 VTB 不再增加。
- [x] 3.6 测试 `/api/v1/tasks/process` 触发 Example 任务，普通读取端点不修改 VTB 或任务状态。

## 4. 文档与验证

- [x] 4.1 更新 Example 模块文档，说明首次奖励、60 秒周期、10 点上限和惰性触发语义。
- [x] 4.2 更新任务系统文档中的 Example 用例和 `time_2`/`meta` 语义。
- [x] 4.3 运行 Example、任务相关测试和 Mythos 完整测试目录，确认不新增 HTTP 路由、数据库表或后台调度器。

## 5. Example 测试界面展示与主动处理

- [x] 5.1 在 `example/index.html` 增加 VTB 自动恢复状态区域和独立的“立即处理”控件，保留顶部只读“刷新”按钮语义。
- [x] 5.2 在 `example/example.js` 加载并保存 `GET /api/v1/tasks` 的 snapshot，展示任务激活状态、`time_2`、倒计时、首次奖励标志、累计发放量和最近发放时间。
- [x] 5.3 实现主动处理流程：每次点击生成新的 UUID `Request-ID`，调用 `POST /api/v1/tasks/process`，请求期间防重复点击，成功后刷新 Credits/Tasks/workspace 状态。
- [x] 5.4 实现任务缺失、未到期、已到期、达到上限和处理失败的界面状态；倒计时只更新显示，不在浏览器到期时自动触发 API 请求。
- [x] 5.5 更新 `example/example.css` 及 Example 文档，保证状态信息和控件在窄屏下可读、可聚焦，并说明只读刷新与主动处理的区别。
- [x] 5.6 通过 Example 浏览器手工验收或现有前端验证方式，确认初始状态、主动处理奖励、未到期处理、到期提示、重复点击保护和注销清理。
