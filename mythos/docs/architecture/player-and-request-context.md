# Player 与请求上下文

## 职责与数据边界

`Player` 是请求级聚合，不对应独立 SQL 表或 ORM Model。其持久化状态分属认证、进度和 Artifact 系统；Factory 以 JWT 的 `PlayerIdentity.player_id`、当前 `AsyncSession` 和冻结 Catalog 创建 Player。

## Interface

| Interface | 所属数据 | 读取 API | 写入限制 |
| --- | --- | --- | --- |
| `ProgressInterface` | `player_progress` 及关联表 | `is_unlocked()`、`is_frontier()` | 仅可写 Player 可调用 `push()`、恢复内部状态 |
| `ArtifactInterface` | `player_artifacts` 及节点表 | `has_artifact()`、`tree_nodes()`、`version` | 仅可写 Player 可调用生成、刷新和删除 |

`Player` 懒加载 Interface；未加载时访问属性会抛出 `PlayerInterfaceNotLoadedError`。Progress、Account、Artifact 和 Credit Interface 实现 `VersionedPlayerInterface`。`Player.state_versions()` 按稳定顺序返回请求的状态版本，未加载或没有有效版本的 Interface 会抛出明确错误。完整 `PlayerFileTree` 缓存由 Player 持有，状态写入成功后通过 `Player.invalidate_cache()` 清空。

## 请求对象、服务与端点

`PlayerInterfaces` 位图为 `PROGRESS`、`ARTIFACTS`、`ACCOUNTS`、`CREDITS`、`HINTS` 和 `ALL`。`get_context()` 创建只读 `RequestContext`，文件动态端点加载全部 Interface，但 `pft4_` 只采集 Artifact 和文件 access_rule 声明的状态版本。`RequestContext` 保存 identity、Player 和 followup 收集器；`CommandContext` 增加 UUID `request_id` 与 `reject()`。

它们没有独立 Router、Registry 或 HTTP 端点；由认证依赖、文件/进度/脚本读取路由和命令执行器使用。相关 API 行为见 [命令契约](../api/commands.md)。

## Example

Example 的文件访问规则读取 `player.accounts` 和 `player.progress`；答案处理器得到 `CommandContext` 后先推进进度，再调用 `player.artifacts.generate_artifact()` 和 `generate_node()`。

## 重要约束

- 只读 Player 不能修改 Interface；写入记录由外层命令事务提交或回滚。
- Interface 可以持有当前 Session 的 ORM 记录，但模块不能取得 Session。
- access rule 是纯读取函数，只能读取 Player 当前已加载的状态。

相关实现：`players/player.py`、`players/factory.py`、`players/dependencies.py`、`players/context.py`。
