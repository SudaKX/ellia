# 进度与 Checkpoint 系统

## 持久化与 Model

进度拥有四张表：`player_progress` / `PlayerProgress` 保存版本及 checkpoint 序号；`player_progress_unlocked_nodes` / `PlayerProgressUnlockedNode` 和 `player_progress_frontier_nodes` / `PlayerProgressFrontierNode` 保存数字节点集合；`player_progress_checkpoints` / `PlayerProgressCheckpoint` 保存当前可恢复快照的本地 `storage_key`。所有玩家级行经外键级联删除。

## Interface 与 Registry

`ProgressInterface` 是 Player 的惰性 Interface，读取 unlocked/frontier、版本和 checkpoint 序号；可写 Player 使用 `push(id, branch_arg)`。它拒绝重复解锁、不可达节点、直接进入 Merge、错误 branch 参数和只读写入。

模块向 `ProgressRegistry` 注册 `NormalProgressNode`、`BranchProgressNode` 或 `MergeProgressNode`。冻结的 `ProgressGraph` 将字符串 ID 映射为稳定 63-bit 数字 ID，验证 DAG、entry、分支和 merge，并提供 `structure_hash`。`BranchTargetSelector` 决定 branch 的目标；AND/OR Merge 由 Interface 自动解析。

## Service、端点和对象

`ProgressService` 提供 `ProgressSnapshot` 和 restore；Router 暴露：

| 方法 | 路径 | Interface | Request-ID |
| --- | --- | --- | --- |
| GET | `/api/v1/progress` | progress 只读 | 否 |
| POST | `/api/v1/progress/checkpoints/restore` | progress 可写 | 是 |

`PendingCheckpoint` 是一次 `push()` 暂存的数字集合和 graph hash。`ProgressCheckpointHook` 在命令提交前将其交给 `LocalCheckpointStore`；后者先原子写 JSON，再添加 `PlayerProgressCheckpoint` 并更新当前序号。

## Example 与重要限制

Example 注册 `example.entry` 和触发 checkpoint 的 `example.completed`。正确验证答案后 `push()` 解锁 completed，hook 产生 checkpoint；重复提交不会再次推进。

checkpoint 恢复会校验文件格式、玩家、序号、graph hash、节点存在性和 frontier 是 unlocked 的子集。SQL 回滚可能留下没有 metadata 的 checkpoint 文件；当前没有清理任务。HTTP DTO 与重试规则见 [进度契约](../api/progress.md)。

相关实现：`registry/progress/`、`players/interfaces/progress.py`、`services/progress/`。
