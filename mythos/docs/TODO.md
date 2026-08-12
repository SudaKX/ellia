# Mythos TODO

## Backend

- [ ] 为 checkpoint restore 在 Request-ID 执行中返回的 `409` 补充 `Retry-After: 1`，并添加对应测试。

## 主动成就授予与 Example 演示

> 前置条件：完成 OpenSpec change `generalize-lifecycle-to-eventbus`，提供事务内的 `VirtualAccountLoggedInEvent`。

- [x] 创建独立 OpenSpec change，定义 `AchievementDefinition.condition` 可选、主动 `grant`、Operation grant drain 与 Check/Effect 合并的契约和事务失败语义。
- [x] 将 `AchievementDefinition.condition` 改为 optional；无 condition 成就不得参与 `/achievement/check` 或普通 Operation 的 condition 扫描，effect 仍必须是带依赖声明的异步 callback。
- [x] 为 `AchievementInterface` 增加仅允许当前活动成就的幂等 `grant(stable_id)`，立即创建 earned state，并在当前 Operation 内缓存待执行的主动 grant stable ID。
- [x] 增加 `drain_grants()` 或等价接口；它只返回并清空当前 Player 聚合本次 Operation 的主动 grant 候选，不提交 transaction，也不执行 effect。
- [x] 调整 `EndpointCommandExecutor`：Operation transaction 提交后合并 drained immediate grants 与 Achievement Check transaction 的 immediate effect 候选，去重并只启动一个 Effect transaction。
- [x] 明确并实现失败语义：主动 grant 已随 Operation 提交时，即使 Condition transaction 失败，仍尝试其已缓存的 immediate effect；Effect transaction 失败时保留 earned state、回滚所有奖励和 claimed_at，并通过既有 warning 返回。
- [x] 确认主动 grant 的重复事件、已 earned 未 claimed 的重试、Request-ID replay、并发 Player 锁和已删除/未知 stable ID 均不会重复奖励或写入无效状态。
- [ ] 在 Example 模块注册 `example.guest-login`：`condition=None`、`immediate=True`、effect 为增加 10 VTB；监听 `VirtualAccountLoggedInEvent` 并仅在 `account_id == example.guest` 时主动 grant。
- [ ] 在 Example 模块注册 `example.vtb-over-15`：`condition=player.credits.vtb > 15`、`immediate=False`、effect 为增加 10 VTB；为 condition/effect 正确声明 CREDITS 依赖。
- [ ] 扩展 Example 页面：认证后的并行加载加入 `GET /achievement`，在现有“提示与 VTB”区域展示成就状态和 earned/claimed 时间，对 available active 成就提供带 Request-ID 的 claim 操作。
- [ ] 更新 Example 页面状态刷新：Guest 虚拟账号登录后刷新 credits 与 achievements；claim 成功或 warning 返回后刷新 achievement 状态，保持现有响应错误展示和请求记录行为。
- [ ] 添加 Registry、Interface、Service、Executor 与 API 测试，覆盖 optional condition、grant/drain、C/D 候选合并和 C/D 失败回滚；增加 Example 端到端测试，验证 Guest 登录的 +10 VTB、`VTB > 15` 的 available 状态和 claim 后的第二次 +10 VTB。
- [ ] 同步 `achievement-system`、`command-execution-boundaries`、Example module/API flow 文档和前端手工验收清单，并运行后端完整测试和 OpenSpec strict validation。
