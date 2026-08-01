# Artifact 与动态文件系统

## 持久化与 Model

Artifact 拥有 `player_artifacts` / `PlayerArtifact` 和 `player_artifact_nodes` / `PlayerArtifactNode`。前者以 `(player_id, artifact_id)` 保存当前对象版本、摘要、媒体类型、尺寸、下载名、生成元数据和时间；后者以 `(player_id, node_id)` 保存运行时路径、revision、display、hidden，并通过 `(player_id, artifact_id)` 外键关联前者。

## Interface、Registry 与数据对象

`ArtifactInterface` 是 Player 的惰性 Interface。`generate(artifact_id, context)` 只允许可写 Player：调用生成器得到 `RawArtifact(data, meta)`，上传对象，upsert 两张表，并清空请求内 `PlayerFileTree` 缓存。`get_tree()` 将静态 `FileTree` 与当前玩家节点合并。

模块先注册 `ArtifactTemplate`，再注册指向它的 `ArtifactNodeTemplate`。模板定义 artifact ID、revision、媒体类型、下载名和异步内容生成器；节点模板定义稳定 ID、默认路径、display、access rule 与节点生成器。运行时 `ArtifactNode` 可改变 path、display、hidden、revision，但不能改变 stable ID 或 artifact locator。Registry 冻结为 `ArtifactCatalog`。

## Service 与端点

没有 Artifact 生成 HTTP 端点，也没有 ArtifactService Router。命令 handler 直接调用 `context.player.artifacts.generate()`；读取经 FileService：

- `GET /api/v1/files/d/ls`、`/d/tree`、`/d/version` 返回静态与 Artifact 合并树。
- 通用 metadata、content URL、download URL 路由也读取合并树。

Artifact content token 使用 `act1_`，payload 绑定 player ID、节点、对象版本和下载名，因而每位玩家的 token 不可互用。

## Example 与限制

Example 注册 `example.recovery-report` 和 `/archive/recovery-report.txt` 节点。验证成功后推进 completed 再生成报告；新的 Request-ID 重复提交不会重新生成。报告与静态 archive result 一起只在动态树中可见。

对象上传发生在 SQL 事务提交前，回滚可能留下 `artifacts/` 前缀下的孤儿对象。`ArtifactCleanupService.sweep(session)` 是无 Router、无调度器的最佳努力维护工具。客户端读取规则见 [文件 API](../api/files.md)。

相关实现：`registry/artifacts/`、`players/interfaces/artifacts.py`、`services/artifacts/cleanup.py`。
