# 成就系统临时设计讨论稿

> 状态：设计讨论稿，尚未实现。
>
> 本文整理当前关于 Mythos 成就系统的讨论结果，用于后续 OpenSpec proposal、design 和实现任务的输入。Task/Auth 事务边界已经根据后续讨论同步到实现和主 OpenSpec；Achievement 本身仍未实现。

## 1. 背景与现状

当前代码中没有实际的 Achievement Registry、Achievement Service、Player Achievement Interface、成就持久化模型或成就 HTTP Router。

现有 OpenSpec 已经为成就系统预留了部分基础设施：

- `command-execution-boundaries` 已定义事务中立的 `AchievementChecker`。
- 已有设计曾预留 operation 之后的 Achievement phase。
- 当前讨论将该 phase 调整为 Operation transaction 提交后的独立事务流程。

当前相关实现边界：

- `RegistryBundle` 在启动期注册谜题内容，并在 freeze 后生成只读 `RuntimeCatalogs`。
- 普通已认证写端点通过 `EndpointCommandExecutor` 执行。
- `POST /tasks/process` 通过独立的 `TaskCommandExecutor` 执行。
- `PipelinedTransaction` 只编排 operation、phase 和 pre-commit hooks，不拥有外层 transaction。
- Task transaction 与 Operation transaction 当前已经是两个独立 transaction。
- `/auth/*` 由独立 Auth Workflow 执行，不纳入本成就系统的自动检查范围。

## 2. 目标范围

本阶段目标：

1. 谜题模块能够注册成就定义。
2. 普通 Player 写端点在业务操作成功后触发一次成就检查。
3. 成就检查和成就奖励使用独立 transaction。
4. 支持 immediate 成就自动发放 effect。
5. 支持当前活动且 available 成就通过 claim 触发 effect，包含 immediate 成就的失败重试。
6. 支持 `POST /achievement/check` 进行补偿检查。
7. 支持 `GET /achievement` 查询活动成就和玩家已达成的历史成就。
8. 支持已从当前 Registry 删除的成就通过启动期 fallback 继续展示历史数据。

明确不包含：

- `/auth/*` 端点不触发 Achievement 检查。
- `POST /tasks/process` 只处理 Task，不重复执行 Achievement C/D 流程。
- 不提供已删除成就的 condition、effect 或补领功能。
- 不提供任意客户端回调 HTTP 路由。
- 不引入后台任务调度器、消息队列或 Outbox。

## 3. 核心术语

### 3.1 活动成就

当前 `AchievementCatalog` 中存在的成就定义。活动成就的 `meta`、`immediate` 和回调均以当前 Registry 为权威来源。

### 3.2 已达成成就

玩家曾经满足过 condition，并在 `player_achievement_states` 中拥有记录的成就。

### 3.3 已删除成就

玩家状态表中存在对应 `stable_id`，但当前 `AchievementCatalog` 中已经找不到该 `stable_id` 的成就。

### 3.4 fallback

应用启动期配置的历史成就展示数据。fallback 不属于当前活动 Registry，不包含 `condition` 或 `effect`，也不能用于补领。

## 4. Registry 设计

### 4.1 成就注册项

注册项暂定为：

```text
AchievementDefinition
{
    stable_id,
    public_id,
    immediate,
    meta,
    condition,
    effect
}
```

建议实际把 `public_id` 作为由 `stable_id` 派生的只读属性，而不是允许谜题模块自由填写。

回调签名：

```text
condition(player: Player) -> bool
effect(player: Player) -> Awaitable[None]
```

注册时校验：

- `stable_id` 唯一且满足稳定 ID 格式。
- `condition` 是同步、单参数 callable。
- `effect` 是异步、单参数 callable。
- `immediate` 是布尔值。
- `meta` 是 JSON 可序列化对象。
- 回调需要声明 Player Interface 依赖。
- Registry freeze 后禁止继续注册。

建议沿用现有 `module_handler(..., dependencies=...)` 机制，使 condition/effect 的依赖可以在 freeze 前被验证并计算依赖并集。

### 4.2 puzzles 注册

外部 `puzzles` 包仍然通过现有入口注册：

```text
puzzles.register_all(registries, *, environment)
    -> registries.achievements.register(...)
```

`RegistryBundle.freeze()` 后生成：

```text
RuntimeCatalogs.achievements
```

`AchievementCatalog` 至少需要提供：

- 根据 `stable_id` 查找定义。
- 根据 `public_id` 查找定义。
- 获取全部活动成就。
- 获取成就 Catalog 版本或稳定指纹。

## 5. public_id 设计

### 5.1 HMAC 方案

成就 public ID 与文件 ID、Hint ID 复用同一个服务端 HMAC 密钥，即当前文件 ID signing key。

建议使用独立域和独立前缀：

```text
a1_ + Base64URL(
    HMAC-SHA256(
        file_id_secret,
        "achievement:v1\0" + stable_id
    )
)
```

设计要求：

- 使用同一个服务端密钥。
- 不复用 `file:v1` 或 `hint:v1` 的 HMAC 域。
- `a1_`、`f1_`、`h1_` 代表不同的 public ID 命名空间。
- public ID 是定位符，不是授权凭据。
- claim 仍然必须检查当前 Player、成就达成状态和领取状态。

### 5.2 密钥轮换影响

因为数据库不保存 public ID，文件 ID signing key 轮换会同时改变：

- 文件 public ID。
- Hint public ID。
- Achievement public ID。

因此当前设计把该密钥视为稳定协议密钥。密钥轮换会使旧 public ID 失效，行为与现有文件 ID 协议保持一致。

## 6. 持久化模型

### 6.1 PlayerAchievementState

建议新增 `player_achievement_states` 表：

```text
player_id                  UUID      PK/FK -> players.id
achievement_stable_id      String    PK
earned_at                  DateTime  NOT NULL
claimed_at                 DateTime  NULL
created_at                 DateTime  NOT NULL
updated_at                 DateTime  NOT NULL
```

复合主键：

```text
(player_id, achievement_stable_id)
```

外键删除策略：

```text
players 删除时级联删除成就状态
```

明确不持久化：

- `meta`
- `immediate`
- `public_id`
- `condition`
- `effect`

没有记录表示未达成，不为所有锁定成就预创建行。

### 6.2 状态计算

```text
没有 PlayerAchievementState       locked
earned_at != null 且 claimed_at 空  available
claimed_at != null                 claimed
```

### 6.3 已删除成就

查询时将当前 Catalog 与玩家状态记录合并：

```text
活动成就：Catalog definition + Player state
已删除成就：Player state + AchievementService fallback
```

已删除成就的 fallback 数据包括：

- `stable_id`
- `meta`
- `immediate`
- 根据 fallback `stable_id` 计算得到的 `public_id`

fallback 不包括：

- `condition`
- `effect`
- claim 能力

已删除成就即使仍然是 `available`，也只允许展示，不能通过 `/achievement/claim/{public_id}` 补领。

### 6.4 fallback 配置

fallback 只允许在应用启动期配置，不提供 HTTP 修改入口。

配置位置可以是：

- 框架内置的兼容模块。
- 外部谜题包保留的历史兼容模块。
- 应用启动组装阶段的固定配置。

建议 `AchievementRegistry.set_fallback()` 只接受数据型 fallback，不接受 effect/condition；同一 stable ID 的后续调用覆盖前值，freeze 时以最后数据为准：

```text
set_fallback(stable_id, meta, immediate)
```

当前 Registry 中仍存在的 `stable_id` 不应配置 fallback；如同时存在，建议启动期拒绝配置冲突。

如果已删除成就没有 fallback，系统使用空 `meta`，并根据 stable ID 继续计算 public ID；该历史成就不提供 claim 或 effect。

## 7. Player Interface

建议新增：

```text
PlayerInterfaces.ACHIEVEMENTS
Player.achievements
PlayerLoader.load_achievements()
```

`AchievementInterface` 只管理玩家已有的成就状态记录：

- 通过 stable ID 判断是否达成。
- 获取已达成状态。
- 创建达成记录。
- 写入 `claimed_at`。
- 为活动 Catalog 和历史 fallback 提供统一查询视图。

它不负责：

- 执行 condition。
- 执行 effect。
- 打开或提交 transaction。
- 解析 HTTP 请求。

## 8. 事务模型

### 8.1 普通 Player 写端点

普通写端点的流程：

```text
Request-ID lease
    │
    ├─ Task Transaction A
    │    执行 Task 批次
    │    全部 Handler 成功
    │    pre-commit hooks 执行一次
    │    commit
    │
    ├─ Operation Transaction B
    │    加载 writable Player
    │    执行业务 Operation
    │    Operation hooks 执行一次
    │    commit
    │
    ├─ Achievement Check Transaction C
    │    执行全部 condition
    │    写入达成记录
    │    commit
    │
    ├─ Achievement Effect Transaction D
    │    执行全部 immediate effect
    │    写入 claimed_at
    │    pre-commit hooks 执行一次
    │    commit
    │
    ├─ 组装最终响应和 warn
    └─ 写入 RequestCache
```

C/D 在 Operation B 提交之后开始，因此 C/D 失败不会回滚 B。

### 8.2 Task Transaction A 失败

任意 Task Handler 出错时：

1. 终止当前 Task 批次。
2. 回滚整个 Task Transaction A。
3. 不执行 Task pre-commit hooks。
4. 不执行 Operation B。
5. 不执行 Achievement C/D。
6. 记录该 Handler 的 `exception` 计数。
7. 停止当前 CommandExecutor。

由于计数发生在失败 transaction 回滚之后，计数必须使用独立的 failure-record transaction：

```text
Task Transaction A
    Handler error
    rollback A

Failure Record Transaction
    lock player/task state
    exception = exception + 1
    commit

CommandExecutor stops
```

failure-record transaction 不执行：

- Task Handler。
- Task pre-commit hooks。
- Operation。
- Achievement 检查。
- Checkpoint 保存。

普通 Handler 异常递增对应任务的 `exception`。取消、数据库错误、hook 错误和进程级异常不应被误记为 Handler 失败计数。

### 8.3 Operation Transaction B 失败

Operation B 失败时：

- 回滚 B。
- 当前 CommandExecutor 停止。
- 不执行 C/D。
- 不生成成功 Operation 响应。
- 不写入 RequestCache。

Task A 如果已经提交，不会因为 B 失败而回滚。这是当前 Task/Operation 分离 transaction 的既有边界。

### 8.4 Achievement Check Transaction C 失败

C 交易中的任意 condition 异常、Player 状态写入异常或 C hooks 异常都会：

- 回滚整个 C transaction。
- 不执行 D。
- 生成 `warn`。
- 不停止 CommandExecutor。
- 使用 Operation 原始响应继续完成请求。
- 将 Operation 响应和 `warn` 一起写入 RequestCache。

`condition == false` 不是错误，只表示该成就本轮不达成。

### 8.5 Achievement Effect Transaction D 失败

D 交易中的任意 effect 异常或 pre-commit hook 异常都会：

- 回滚整个 D transaction。
- 回滚本次 D 内所有奖励和 `claimed_at` 更新。
- 保留已经提交的 C 达成记录。
- 生成 `warn`。
- 不停止 CommandExecutor。
- 将 Operation 响应和 `warn` 写入 RequestCache。

因此 immediate 成就可能处于：

```text
condition 已达成
effect 尚未成功
claimed_at 为空
```

后续可以通过 `POST /achievement/check` 再次尝试 effect。

## 9. PipelinedTransaction 复用

Task 批次和 Effect 批次都使用批次级 `PipelinedTransaction`：

```text
PipelinedTransaction.run(session, player, batch_operation)
```

其中：

- `batch_operation` 执行全部 Handler 或全部 Effect。
- `pre_commit_hooks` 在 batch operation 完成后执行一次。
- hooks 成功后由外层 transaction owner 提交 transaction。
- Pipeline 不拥有 transaction。

Task Handler 和 Achievement Effect 不再使用各自的 per-handler/per-effect savepoint。

这同时解决了延迟 hook 时 pending checkpoint 在 Player reload 后丢失的问题，因为失败 Handler 不再继续 reload 后执行剩余 Handler；整个 Task transaction 会直接失败。

`ProgressCheckpointHook` 在完整成功批次末尾执行一次，消费该 Player 当前批次内的所有 pending checkpoints。失败批次不保存 checkpoint。

## 10. HTTP CommandExecutor

### 10.1 EndpointCommandExecutor

负责：

- Request-ID lease。
- Task A 和 Operation B 的 transaction 编排。
- Operation 响应构造。
- Operation 成功后的 Achievement C/D 调用。
- C/D 失败转换为 `warn`。
- 最终响应写入 RequestCache。

如果 Task A 或 Operation B 失败，直接抛出错误，不创建成功缓存。

如果 C/D 失败，捕获错误并继续完成最终响应。

### 10.2 TaskCommandExecutor

只负责：

- Request-ID lease。
- Task Transaction A。
- Task Handler 批次 Pipeline。
- Task 报告。

`POST /tasks/process` 不执行 Achievement C/D。

Task 失败时：

- 回滚 Task transaction。
- 独立 transaction 递增失败 Handler 的 exception。
- 不缓存成功响应。
- CommandExecutor 停止。

### 10.3 AchievementCommandExecutor

独立于 `EndpointCommandExecutor`，参考当前 `TaskCommandExecutor`。

负责：

- `POST /achievement/check`。
- `POST /achievement/claim/{public_id}`。
- Achievement C/D transaction。
- C/D 错误收集为 warn。
- RequestCache。

它不执行 Task A，也不复用普通 Player Operation。

## 11. HTTP 响应格式

当前命令成功响应格式为：

```json
{
  "content": {},
  "followups": []
}
```

C/D 错误时扩展为：

```json
{
  "content": {},
  "followups": [],
  "warn": [
    {
      "code": "achievement-check-failed",
      "stage": "achievement.check",
      "message": "Achievement check was not completed."
    }
  ]
}
```

Effect 错误示例：

```json
{
  "content": {},
  "followups": [],
  "warn": [
    {
      "code": "achievement-effect-failed",
      "stage": "achievement.effect",
      "public_id": "a1_...",
      "message": "Achievement reward was not applied. Retry with /achievement/check."
    }
  ]
}
```

设计要求：

- `warn` 是数组。
- 没有警告时省略该字段。
- `warn` 随最终 Operation 响应一起缓存。
- C/D 原始异常只写服务端日志。
- Task/Operation 主事务错误不放入 `warn`，使用现有 Problem Details 错误格式。
- Task Handler 的可预期失败计数不作为成功响应返回，因为该 CommandExecutor 已经停止。

## 12. HTTP API

### `GET /api/v1/achievement`

只读查询，不执行 condition，不创建状态。

返回活动成就和历史已达成成就：

```json
{
  "items": [
    {
      "public_id": "a1_...",
      "meta": {},
      "immediate": false,
      "status": "locked"
    },
    {
      "public_id": "a1_...",
      "meta": {},
      "immediate": true,
      "status": "claimed",
      "earned_at": "...",
      "claimed_at": "..."
    }
  ]
}
```

### `POST /api/v1/achievement/check`

要求 Bearer JWT 和 UUID `Request-ID`。

行为：

- 不执行 Task。
- 执行 C transaction。
- C 成功后执行 D transaction。
- C/D 错误写入 `warn`。
- 请求本身不因 C/D 错误停止。
- 响应和 warn 写入 RequestCache。

### `POST /api/v1/achievement/claim/{public_id}`

要求 Bearer JWT 和 UUID `Request-ID`。

行为：

- 只允许当前活动成就领取。
- 已删除成就无论是否有 fallback，都不提供补领。
- 未达成成就返回状态错误。
- 已领取成就保持幂等。
- Effect 失败写入 `warn`，不重复执行普通 Operation。

## 13. 需要更新的现有规范

当前 `lazy-task-execution` 中关于 Task Handler savepoint、失败后继续执行和外层 transaction 内递增 exception 的描述与本设计冲突，后续 OpenSpec 变更需要修改：

- Handler 失败改为整个 Task transaction 回滚。
- exception 改由回滚后的独立 failure-record transaction 递增。
- Handler 不再失败后继续处理后续任务。
- pre-commit hooks 改为成功批次末尾执行一次。
- Task 失败不保存 checkpoint。

## 14. 验证重点

实现时至少需要覆盖：

1. 多个 Task Handler 全部成功时 hook 只执行一次。
2. 任一 Task Handler 失败时所有 Task 状态和 checkpoint 回滚。
3. Task 回滚后 exception 在独立 transaction 中递增。
4. Task 失败不会启动 Operation。
5. Operation 失败不会启动 Achievement C/D。
6. C condition 失败会回滚 C 并生成 warn。
7. D effect 失败会回滚 D、保留 C 达成记录并生成 warn。
8. C/D 失败时 Operation 响应仍写入 RequestCache。
9. Request-ID 重放返回包含相同 warn 的缓存响应。
10. `/tasks/process` 不执行 Achievement C/D。
11. 已删除成就只通过启动期 fallback 查询，不允许 claim。
12. public ID 使用相同 HMAC 密钥但使用独立 `achievement:v1` 域。

## 15. Task/Auth 事务边界补充

Task 系统与 Auth Workflow 解耦：

- `register`、`login`、`logout` 和 `refresh` 不执行 Task Handler。
- Construct lifecycle 可以通过 `Player.tasks.add_task()` 激活任务，但只写入待处理任务状态。
- `logout` 不调用 `/tasks/process`。
- `/tasks/process` 的调用时机由前端决定。
- 普通非 Auth 写端点现有的自动 Task phase 暂时保留。

Task Handler 的执行边界：

- CommandExecutor 负责锁定并加载一次 Player。
- CommandExecutor 负责组织 `PipelinedTransaction`。
- 一个 Task transaction 只创建一个 batch savepoint。
- 全部 Handler 成功后统一运行一次 pre-commit hooks。
- 普通 Handler 异常回滚整个 batch savepoint，在外层 Task transaction 中增加 `exception`，提交计数后停止命令；取消和其他 `BaseException` 不计数并直接失败。
- Handler 错误不继续执行后续 Handler，不重载 Player，不执行 Operation 或 Achievement phase。
- Hook、数据库、JSON 和提交错误不计入 Handler `exception`，直接使 Task transaction 失败。
