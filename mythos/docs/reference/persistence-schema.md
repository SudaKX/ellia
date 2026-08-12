# 持久化总览

SQLite 是玩家和发布登记的权威数据源；RustFS/S3 保存文件字节，本地文件系统保存 checkpoint 与 Catalog 快照 JSON。当前 migration head 为 `0012_player_achievements`，共有十六张表。对象存储 bucket versioning 已停用，VersionId 不进入 Mythos 持久化模型。

| 表 | ORM Model | 所属系统 | 关键关系 |
| --- | --- | --- | --- |
| `players` | `PlayerRecord` | 认证/生命周期 | 玩家主键；一对一认证和进度；`constructed_at` 标记 Construct 完成 |
| `player_auth` | `PlayerAuth` | 认证 | `players.id` 外键；密码与 refresh 凭据摘要 |
| `player_progress` | `PlayerProgress` | 进度 | `players.id` 外键；版本和 checkpoint 序号 |
| `player_progress_unlocked_nodes` | `PlayerProgressUnlockedNode` | 进度 | `(player_id, node_id)` 主键 |
| `player_progress_frontier_nodes` | `PlayerProgressFrontierNode` | 进度 | `(player_id, node_id)` 主键 |
| `player_progress_checkpoints` | `PlayerProgressCheckpoint` | 进度 | `(player_id, sequence)` 主键；本地文件 `storage_key` |
| `static_file_registrations` | `StaticFileRegistration` | 文件 | source locator、对象 key、SHA-256 摘要和退休时间 |
| `player_artifacts` | `PlayerArtifact` | Artifact | `(player_id, artifact_id)` 主键；玩家当前对象版本 |
| `player_artifact_nodes` | `PlayerArtifactNode` | Artifact | `(player_id, node_id)` 主键；复合外键指向 Artifact |
| `player_artifact_states` | `PlayerArtifactState` | Artifact | 玩家独立的单调 PlayerVersion |
| `player_virtual_accounts` | `PlayerVirtualAccount` | VirtualAccount | `(player_id, account_id)` 主键；用户名在玩家范围唯一，保存密码哈希和登录统计 |
| `player_virtual_account_states` | `PlayerVirtualAccountState` | VirtualAccount | 当前账号及版本；复合外键保证当前账号属于玩家 |
| `player_credits` | `PlayerCredits` | Credits | 玩家 VTB、版本与更新时间；VTB 不可为负 |
| `player_hint_disclosures` | `PlayerHintDisclosure` | Hint | `(player_id, hint_stable_id)` 主键，保存已购买资格与时间 |
| `player_achievement_states` | `PlayerAchievementState` | Achievement | `(player_id, achievement_stable_id)` 主键；保存 earned/claimed 时间与审计时间 |
| `player_task_states` | `PlayerTaskState` | LazyTask | `(player_id, task_id)` 主键，保存任务时间、错误次数和 JSON meta |

## 非 SQL 状态

- checkpoint 文件：`LocalCheckpointStore` 写入 `{player_id, sequence, graph_hash, unlocked_node_ids, frontier_node_ids}`，数据库仅保存 storage key。
- 静态对象：`static/<module>/<relative_path>`；内容变化时覆盖固定 key，FileTree 通过 `snv1_` 和 `fcv1_` 识别变化。
- Artifact 对象：`artifacts/{player_id}/{artifact_version}`；上传失败或 SQL 回滚后的孤儿由 `ArtifactCleanupService` 最佳努力清理。
- Artifact Catalog 快照：本地 `artifact-template-catalog.json`；启动期以最后成功快照计算模板差量。
- VirtualAccount Catalog 快照：本地 `virtual-account-template-catalog.json`；启动期以当前 Catalog 清理 SQL 中已退休账号类型。
- Task Registry 快照：本地任务 Catalog 身份集合 JSON；启动期清理当前 Catalog 中不存在的 `player_task_states`，不保存玩家任务状态或 Handler 依赖。
- `RequestCache`：仅当前 Python 进程内存，受 TTL 和 maxsize 限制。

`0004_static_file_registrations` 和 `0005_player_artifacts` 中仍能看到 `source_mtime_ns`、`object_version_id` 等历史列，因为 migration 文件必须保留历史 schema 定义。`0010_content_versions` 的 upgrade 已删除这些列；由于 provider VersionId 已被丢弃，该 migration 明确不可逆，downgrade 会立即失败。migration head 和当前 ORM 均不再使用这些列。

迁移顺序：`0001_initial_auth`、`0002_player_graph_progress`、`0003_remove_legacy_progress_fields`、`0004_static_file_registrations`、`0005_player_artifacts`、`0006_artifact_template_versions`、`0007_virtual_accounts`、`0008_player_lifecycle`、`0009_player_credits_and_hints`、`0010_content_versions`、`0011_player_tasks`、`0012_player_achievements`。运行迁移时从 `mythos/` 使用 `python -m alembic -c alembic.ini upgrade head`。
