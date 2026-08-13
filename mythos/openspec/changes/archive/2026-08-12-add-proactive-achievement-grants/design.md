## Context

成就系统当前要求每个 `AchievementDefinition` 有同步 condition，并由 `AchievementService.check()` 在普通 Operation 提交后的 Check transaction 中扫描。EventBus 已提供 `VirtualAccountLoggedInEvent` 等事务内模块扩展点，但 listener 无法将一个成就标记为达成而不借用错误的 condition。

现有 Operation B、Check C 和 Effect D 已是独立 transaction：B 成功后 C 写 earned state，D 执行 immediate effect 并写 claimed_at。C/D 的异常不会回滚 B，并通过 warning 进入已缓存的响应。本 change 必须保持 Service 不拥有 transaction、EventBus listener 不直接执行奖励，以及一个请求最多只创建一个 Effect batch 的边界。

## Goals / Non-Goals

**Goals:**

- 允许无 condition 的活动成就由模块 EventBus listener 或其他 Operation 逻辑主动授予。
- 使主动 grant 的 earned state 属于 Operation B，而 effect 仍在 B 提交后的独立 D transaction 中执行。
- 将主动 immediate grants 与 C 的 immediate effect 候选合并、去重、稳定排序，并用单个 D batch 执行。
- 明确 C 或 D 失败、重放和重复事件下的行为，保持奖励不重复。

**Non-Goals:**

- 不注册 Example 成就，不添加 VTB 奖励逻辑，不修改前端或 HTTP API。
- 不允许客户端直接传 stable ID 主动授予成就，不新增 grant Router。
- 不让 Auth workflow、Task-only command 或 EventDispatcher 本身自动执行 Achievement C/D。
- 不增加持久化 grant queue、跨请求重试队列、消息代理或数据库 schema。

## Decisions

### condition 为 optional，定义仍始终要求 effect

`AchievementDefinition.condition` 改为 `AchievementCondition | None`。有 condition 的定义保留原同步 callback、单参数和依赖声明校验；`None` 不进行 condition callback 校验。effect 对所有成就仍必填、异步、单参数且要求依赖声明。

无 condition 定义不参与 `check()`，因此 `POST /achievement/check` 和正常 Operation 的自动 C 都不能授予它。其 Catalog dependencies 只包含 effect dependencies。这样主动授予的触发权限保持在模块已注册的事务内 handler，而非公开检查 API。

### grant 属于 Player Interface，并以 Catalog 活动集合限制目标

`AchievementInterface` 构造时接收冻结 Catalog 的活动 stable ID 集合。新增 `grant(stable_id)`：

1. 拒绝只读 Player。
2. 拒绝不在活动集合中的 stable ID，因而不能向 fallback、已删除或未知成就写状态。
3. 通过既有 `earn()` 幂等创建或读取 earned state。
4. 将 stable ID 加入当前 Interface 的 pending grant 集合，包含已 earned 但未 claimed 的重复 grant，以支持曾失败 immediate effect 的事件重试。

`drain_grants()` 返回当前 pending stable ID 的不可变结果并清空集合；它不访问 Session、不执行 effect、不改变 claimed_at。pending 集合仅驻留在 Operation B 的 Player aggregate，因此 B 失败时 aggregate 与数据库都被丢弃，B 成功后 executor 立即取得候选。

不将 grant 放入 AchievementService：模块的自然扩展点已经拥有 Player，且 Interface 是 earned state 的唯一写入所有者。Service 保持 check、candidate 规范化和 effect batch 的事务中立领域逻辑。

### Operation 强制加载 ACHIEVEMENTS 并返回 drained grants

配置 AchievementService 的 EndpointCommandExecutor 在 B 加载 Player 时将 `PlayerInterfaces.ACHIEVEMENTS` 并入 operation interfaces。Operation 成功并完成 Pipeline 后，executor 在 B transaction 内调用 `context.player.achievements.drain_grants()`，将结果随内部 operation outcome 返回；外部 HTTP response 不暴露 stable ID。

这允许 EventBus listener 在 `/vac/login` 等 endpoint Operation 中调用 `player.achievements.grant()`，又不会让 EventDispatcher 或 Domain Service 获得 executor、Session ownership 或 HTTP 依赖。

### D 的候选来自 grants 与 Check，且 C 失败不丢弃 grants

`AchievementService` 提供稳定的 immediate effect 候选规范化：只保留当前活动、`immediate=True` 的 stable ID，并按 Catalog 顺序去重。Check 返回的 candidates 保留现有语义：已 earned 且未 claimed 的 immediate condition 成就可以补偿重试。

executor 将 B drained grants 与 C `effect_stable_ids` 合并后规范化。若 C 抛出异常，executor 保留 `achievement-check-failed` warning，但仍仅用 drained grants 构成 D candidates。这是必要的，因为主动 grant 的 earned state 已经随 B 提交，不能因独立 C 失败而永久遗漏它的 immediate 奖励。

若没有 immediate candidates，D 不启动。若存在 candidates，D 只启动一次；任一 effect 或 hook 异常仍回滚整个 D，保留 B/C 已提交的 earned state，并加入 `achievement-effect-failed` warning。

### 幂等性沿用现有 Player 锁与 RequestCache

同一 Request-ID 在 lease replay 前不会运行 B、C 或 D。不同请求由 PlayerLoader 的玩家锁串行化；第二个请求读到已 earned/claimed state 后不会重复 effect。重复主动 grant 在 claimed 后可进入 pending，但 candidate 规范化和 `apply_effects()` 都跳过已 claimed state；在 available 状态时可重新成为 immediate candidate，用于补偿先前 D 失败。

## Risks / Trade-offs

- [C 失败后主动 effect 仍执行] -> 这是主动 grant 已提交于 B 的必要补偿；D 仅消费 B drained grants，绝不执行未完成 C 的 condition 候选。
- [模块误传 stable ID] -> Interface 仅接受 Catalog 的活动 ID，未知、fallback 和已删除 ID 立即失败并使当前 B 回滚。
- [操作未加载 ACHIEVEMENTS] -> 配置 AchievementService 的 EndpointCommandExecutor 强制把该 Interface 并入 B 的加载位图。
- [重复事件再次发奖] -> earned/claimed state、候选去重、单 D batch 和玩家锁共同保证 effect 至多在 claimed 状态前成功一次；D 失败时重试是有意行为。
- [effect 的外部不可逆副作用] -> 保持既有约束，effect 仅应使用事务内 Player Interface；可靠外部副作用仍需要独立 Outbox 设计。

## Migration Plan

1. 扩展 Achievement definition/registry/catalog 与 PlayerLoader/Interface，不修改持久化 schema。
2. 将 Service 与 EndpointCommandExecutor 改为收集、规范化和执行合并 candidates。
3. 补充单元、executor 与 API 兼容性测试，确保已有 condition/claim/check 行为保持。
4. 发布后，后续 Example change 可安全注册无 condition 的 Guest 登录成就并从 `VirtualAccountLoggedInEvent` 调用 grant。
5. 回滚代码时已写入的 earned states 保留；旧版本仍可将活动定义按普通历史状态展示，不会删除玩家数据。

## Open Questions

- 无。主动 grant 的来源由模块逻辑决定；框架只负责活动 ID 校验、事务参与和 effect 延迟执行。
