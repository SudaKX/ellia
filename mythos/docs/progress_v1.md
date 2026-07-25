# Progress V1

## Node Registration

模块向 `registries.progress` 注册 `NormalProgressNode`、`BranchProgressNode` 或 `MergeProgressNode`。每个节点使用全局唯一的可读 `id`，并以 `next` 声明字符串后继 ID。模块不使用持久化数字 ID。

`ProgressGraph` 在 freeze 时从 `id` 生成稳定的正 63 位数字 ID，检查碰撞、DAG、entry、fan-out、fan-in 和 merge 规则。Graph 按节点 ID 和有向边生成 `structure_hash`；节点类型、checkpoint 标记和 Branch 实现不参与该 Hash。

## Player State

每个玩家保存 `unlocked_nodes` 与 `frontier_nodes` 的数字节点 ID 集合。frontier 必须是 unlocked 的子集；entry 节点在注册玩家时同时写入两个集合。

模块命令通过 `context.player.progress.push(id, branch_arg)` 推进。Normal 从当前 frontier 的后继进入；Branch 无参数进入分支、有参数时调用 `how` 选择声明后的继；Merge 不能直接进入，Interface 在每次 push 后自动解析满足 AND 或 OR 条件的 merge。

## Checkpoints

带 `triggers_checkpoint=True` 的节点在一次 push 的最终稳定状态触发 checkpoint。Interface 暂存 unlocked/frontier 数字集合、玩家 ID、序号和 Graph Hash；CommandTransactionExecutor 的 pre-commit hook 将 JSON 写至同目录临时文件、`fsync` 后以 `os.replace` 原子改名，再写入 checkpoint metadata。

`current_checkpoint_sequence = -1` 表示没有可恢复 checkpoint；`next_checkpoint_sequence` 从零开始且单调递增。恢复当前 checkpoint 时，ProgressService 校验文件玩家 ID、序号、Graph Hash 与节点集合后覆盖 unlocked/frontier。

## HTTP API

```text
GET  /api/v1/progress
POST /api/v1/progress/checkpoints/restore
```

恢复是命令端点，需要 JWT 与 `Request-ID`。进度读取响应使用字符串节点 ID，数据库与 checkpoint 文件使用数字节点 ID。
