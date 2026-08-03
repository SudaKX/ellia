# 持久化总览

SQLite 是玩家和发布登记的权威数据源；RustFS/S3 保存文件字节和版本，本地文件系统保存 checkpoint 与 Catalog 快照 JSON。当前 migration head 为 `0007_virtual_accounts`，共有十二张表。

| 表 | ORM Model | 所属系统 | 关键关系 |
| --- | --- | --- | --- |
| `players` | `PlayerRecord` | 认证 | 玩家主键；一对一认证和进度 |
| `player_auth` | `PlayerAuth` | 认证 | `players.id` 外键；密码与 refresh 凭据摘要 |
| `player_progress` | `PlayerProgress` | 进度 | `players.id` 外键；版本和 checkpoint 序号 |
| `player_progress_unlocked_nodes` | `PlayerProgressUnlockedNode` | 进度 | `(player_id, node_id)` 主键 |
| `player_progress_frontier_nodes` | `PlayerProgressFrontierNode` | 进度 | `(player_id, node_id)` 主键 |
| `player_progress_checkpoints` | `PlayerProgressCheckpoint` | 进度 | `(player_id, sequence)` 主键；本地文件 `storage_key` |
| `static_file_registrations` | `StaticFileRegistration` | 文件 | source mtime、对象 key/version、摘要和退休时间 |
| `player_artifacts` | `PlayerArtifact` | Artifact | `(player_id, artifact_id)` 主键；玩家当前对象版本 |
| `player_artifact_nodes` | `PlayerArtifactNode` | Artifact | `(player_id, node_id)` 主键；复合外键指向 Artifact |
| `player_artifact_states` | `PlayerArtifactState` | Artifact | 玩家独立的单调 PlayerVersion |
| `player_virtual_accounts` | `PlayerVirtualAccount` | VirtualAccount | `(player_id, account_id)` 主键；用户名在玩家范围唯一，保存密码哈希和登录统计 |
| `player_virtual_account_states` | `PlayerVirtualAccountState` | VirtualAccount | 当前账号及版本；复合外键保证当前账号属于玩家 |

## 非 SQL 状态

- checkpoint 文件：`LocalCheckpointStore` 写入 `{player_id, sequence, graph_hash, unlocked_node_ids, frontier_node_ids}`，数据库仅保存 storage key。
- 静态对象：`static/<module>/<relative_path>`；每次 FileTree 固定一个对象 VersionId。
- Artifact 对象：`artifacts/{player_id}/{artifact_id}/{artifact_version}/{digest}`；上传失败或 SQL 回滚后的孤儿由 `ArtifactCleanupService` 最佳努力清理。
- Artifact Catalog 快照：本地 `artifact-template-catalog.json`；启动期以最后成功快照计算模板差量。
- VirtualAccount Catalog 快照：本地 `virtual-account-template-catalog.json`；启动期以当前 Catalog 清理 SQL 中已退休账号类型。
- `RequestCache`：仅当前 Python 进程内存，受 TTL 和 maxsize 限制。

迁移顺序：`0001_initial_auth`、`0002_player_graph_progress`、`0003_remove_legacy_progress_fields`、`0004_static_file_registrations`、`0005_player_artifacts`、`0006_artifact_template_versions`、`0007_virtual_accounts`。运行迁移时从 `mythos/` 使用 `python -m alembic -c alembic.ini upgrade head`。
