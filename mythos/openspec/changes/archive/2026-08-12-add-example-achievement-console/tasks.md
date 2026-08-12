## 1. Example 成就注册

- [x] 1.1 在 `puzzles/example` 定义并注册 `example.guest-login`：无 condition、immediate、依赖 Credits 的 10 VTB effect，以及所需展示元数据。
- [x] 1.2 增加 `VirtualAccountLoggedInEvent` listener：仅为 `example.guest` 授予 `example.guest-login`，声明成就依赖且不在模块内处理 transaction。
- [x] 1.3 定义并注册 `example.vtb-over-15`：依赖 Credits 的 `vtb > 15` condition、非 immediate 的依赖 Credits 10 VTB claim effect，以及所需展示元数据。

## 2. Example 控制台

- [x] 2.1 扩展 `example/example.js` 的认证 workspace state 和并行加载，以读取、渲染和清理成就快照。
- [x] 2.2 在 `example/index.html` 既有“提示与 VTB”区域增加紧凑成就列表，并在 `example/example.css` 增加状态、时间、immediate 状态和领取控件的响应式样式。
- [x] 2.3 实现逐成就 claim pending state、新 UUID Request-ID 处理、可读错误，以及成功或 warning 领取响应后的权威 workspace 刷新。
- [x] 2.4 在独立且有上限的控制台活动 state 中捕获成功命令响应的 `followups`，在命令结果附近渲染 action 与防御性 data 输出，并在认证清理时重置。
- [x] 2.5 确保 Guest 虚拟账号登录和其他既有 workspace 刷新流程重新加载 Credits 与成就，不改变请求记录或任务恢复语义。
- [x] 2.6 在成就区域添加显式检查控件，使用新的 Request-ID 调用既有 check command，并在成功或 warning 响应后刷新快照。
- [x] 2.7 在首次 Guest 登录成就达成时通过 EventContext 发送 `achievement-earned` followup，供页面命令活动展示。

## 3. 验证

- [x] 3.1 扩展 Example 模块/API 端到端测试，验证 Guest 登录达成并立即奖励 `example.guest-login`，重复或非 Guest 登录不重复奖励，且成就快照报告结果状态。
- [x] 3.2 增加聚焦覆盖，验证 `example.vtb-over-15` 仅在大于 15 VTB 时 available、显式领取授予 10 VTB，以及精确阈值行为。
- [x] 3.3 增加或扩展静态控制台验证，覆盖成就快照加载、claim Request-ID 与刷新行为、有上限 followup 渲染和认证清理。
- [x] 3.4 增加独立玩家先登录 Administrator 的端到端覆盖，验证非 Guest 登录不会授予 Guest 成就。
- [x] 3.5 验证首次 Guest 登录响应包含成就 followup，重复登录不重复发送。

## 4. 文档与验证

- [x] 4.1 更新 Example 模块和 API flow 文档，说明两个成就流程、控制台领取交互和 followup 活动展示。
- [x] 4.2 更新 Example 浏览器手工验收清单，覆盖即时 Guest 奖励、阈值领取奖励和 followup 活动清理。
- [x] 4.3 从 `mythos/` 运行聚焦 Example 和 achievement 测试，再运行 `mythos/.venv/Scripts/python.exe -m pytest tests`。
- [x] 4.4 运行 `openspec validate add-example-achievement-console --strict --no-interactive` 并解决全部验证问题。
