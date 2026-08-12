## 1. Definition 与 Player Interface

- [x] 1.1 将 `AchievementDefinition.condition` 改为 optional，并更新 Registry callback 校验、依赖聚合和 Catalog fingerprint，使 grant-only definition 只要求 effect。
- [x] 1.2 向 AchievementInterface 注入当前活动 achievement stable ID 集合，新增拒绝非活动 ID 的幂等 `grant(stable_id)`。
- [x] 1.3 实现聚合本地的 `drain_grants()`，确保它返回并清空当前 Operation 的 pending IDs，且不执行 effect 或管理 transaction。
- [x] 1.4 更新 PlayerLoader 及 Interface 构造测试，覆盖只读、未知/fallback ID、重复 grant、已 claimed 和 drain 行为。

## 2. Service 与执行器事务编排

- [x] 2.1 修改 AchievementService.check()，跳过 condition 为 null 的定义；提供对活动 immediate candidates 的稳定排序和去重规范化入口。
- [x] 2.2 修改 EndpointCommandExecutor 的 Operation Player 加载与内部 outcome，在 B transaction 成功后 drain 主动 grants 并保留其候选到 C/D 编排。
- [x] 2.3 合并 drained grants 与 Check immediate candidates，以一个 D batch 执行；C 失败时仅以 drained grants 继续 D，并聚合现有 check/effect warning。
- [x] 2.4 保持 AchievementCommandExecutor 的 check/claim、TaskCommandExecutor、Auth workflow 和所有现有 HTTP URL 不变。

## 3. 测试与兼容性

- [x] 3.1 扩展 Registry/Catalog/Service 测试，覆盖 optional condition、grant-only 成就不被 check 扫描、effect dependency 和 Catalog 版本变化。
- [x] 3.2 扩展 Interface/Executor 测试，覆盖 B 内 earned 落表、grant drain、C/D 候选合并、稳定去重、D 整体回滚和 Request-ID replay。
- [x] 3.3 添加 C 失败后仍执行主动 immediate effect，以及重复事件对 available 成就补偿、对 claimed 成就不重复奖励的测试。
- [x] 3.4 回归现有 achievement API、普通 endpoint command、Task-only command 和 EventBus 测试，确认无公开 grant API 或 Example 成就注册。

## 4. 文档与验证

- [x] 4.1 同步 Achievement 系统、命令事务、API 文档与 TODO，明确主动 grant 的模块边界、C/D 失败语义和后续 Example change 的依赖。
- [x] 4.2 运行 `mythos/.venv` 的成就和命令相关聚焦测试及完整 `tests` 套件。
- [x] 4.3 运行 `openspec validate add-proactive-achievement-grants --strict`，并确认本 change 不包含 Example 成就、前端界面、数据库迁移或持久化消息系统。
