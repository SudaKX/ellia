## 背景

成就框架现已支持无条件定义、事件驱动的 `grant()`、延迟的 grant drain，以及普通命令事务后合并执行即时 effect。Example 模块尚未注册成就，因此不能演示事件驱动或条件扫描路径。其静态 `/example/` 控制台已加载认证后的 workspace 快照并记录 HTTP 请求，但尚未加载成就，也没有展示成功命令返回的 followup 数据。

本 change 限于 Example 演示模块及其静态控制台。Registry 内容会在启动后冻结，模块不拥有 session 或 transaction，命令响应必须保留由既有 executor 拥有的事务边界。

## 目标与非目标

**目标：**

- 演示在 Guest 虚拟账号登录后主动授予的、即时生效的 Example 成就。
- 演示在玩家 VTB 大于 15 后变为可领取、仅在显式领取时发放奖励的条件成就。
- 让既有 Example 控制台展示权威的成就快照、支持领取，并显示成功命令响应中的 followup。
- 保持既有 VTB 恢复流程、请求记录与错误展示不变。

**非目标：**

- 修改共享 Achievement API、EventBus、命令 executor、数据库 schema 或成就 HTTP 契约。
- 新增路由、Service、调度器、前端框架或持久化的客户端活动历史。
- 让只读 workspace 刷新检查、领取或奖励成就。

## 决策

### 在模块 Registry 中注册两个 Example 定义

`example.guest-login` 不设置 condition、设置为 immediate，并声明一个依赖 Credits 的 effect 来授予 10 VTB。`VirtualAccountLoggedInEvent` listener 仅在登录账号为 `example.guest` 时调用 `player.achievements.grant()`。

`example.vtb-over-15` 将声明依赖 Credits 的 `player.credits.vtb > 15` 条件，设置为非 immediate，并在领取时通过依赖 Credits 的 effect 授予 10 VTB。这使用框架预期的两个入口，而非在 Example progress 或 task meta 中实现成就状态。

考虑过的替代方案：直接在账号 listener 中授予 Guest 奖励会绕过 earned 和 claimed 状态；为登录成就使用 condition 则不能演示无 condition 的主动 grant，且可能被不相关的命令评估。

### 将成就作为认证后的 workspace 快照加载

控制台将在既有认证后的并行读取中加入 `GET /achievement`，并将响应保留在 workspace state 中。渲染位于既有“提示与 VTB”区域，与驱动 VTB 阈值条件的数据相邻。每一项展示标识、状态、immediate 标记、达成时间、领取时间，并仅为活动且 available 的成就提供领取控件。

考虑过的替代方案：仅在打开区域时加载列表会为小型诊断控制台增加特殊加载状态，并让 VTB 与成就视图在刷新后不同步。

### 通过既有命令端点并使用新的 Request-ID 领取

每次领取操作都将使用新的 UUID Request-ID 调用既有成就领取命令，在 pending 时禁用已操作控件，并在解析成功响应后刷新 workspace，包括带 warning 的响应。这样可确保 earned/claimed 状态和 resulting Credits 余额来自服务端。

考虑过的替代方案：乐观地将成就标为 claimed 会错误表示 effect 回滚和 warning 结果。

### 将 followup 作为有上限的临时命令活动保留

`readJson()` 将识别成功 payload 中的 `followups`，并将有效项追加到独立且有上限的活动集合中。命令结果控件附近的紧凑渲染会展示每个 followup 的 action 和 JSON 兼容 data。认证清理将与其他 workspace 数据一起重置此集合；网络请求记录保持独立且不变。

考虑过的替代方案：复用 `state.events` 会混合传输诊断与领域通知，而跨会话保存 followup 会显示前一位玩家的命令结果。

## 风险与权衡

- [VTB 变更命令后，过期控制台仍可将阈值成就展示为不可用] -> 在成功领取和既有相关命令后刷新 workspace，包括 Guest 虚拟账号登录。
- [命令响应可能包含格式错误或异常大的 followup 数据] -> 仅渲染 action 为字符串的数组项，防御性序列化 data，并保持小的固定活动上限。
- [重复 Guest 登录可能触发重复事件] -> 依赖既有幂等的 `grant()` 行为及既有 effect 执行语义。
- [初始 VTB 配置可能影响何时达到阈值] -> 通过支持的 Example 流程测试可观察的 `VTB > 15` 转换，而不是假设固定初始余额。

## 迁移计划

1. 在 Example Registry 初始化期间注册两个定义和 Guest 登录 listener。
2. 扩展 Example 控制台状态、标记、样式和命令 handler。
3. 增加 Example 端到端覆盖，并更新 Example 文档和手工验收说明。
4. 无数据迁移地部署。既有玩家接收新的活动定义；成就状态仅由普通 grant、条件检查和领取流程创建。

回滚仅需还原模块和静态控制台改动。既有 earned 成就记录仍由标准成就系统管理，不需要 schema 或迁移回滚。

## 待决问题

无。
