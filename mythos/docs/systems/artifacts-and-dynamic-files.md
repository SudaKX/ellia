# Artifact 与动态文件系统

## 持久化与 Model

Artifact 拥有 `player_artifacts` / `PlayerArtifact`、`player_artifact_nodes` / `PlayerArtifactNode` 与 `player_artifact_states` / `PlayerArtifactState`。前两者分别保存已应用的 `ArtifactVersion`、`ArtifactNodeVersion`、对象引用和运行时节点属性；状态表保存玩家独立、单调递增的 `PlayerVersion`。

## Interface、Registry 与数据对象

`ArtifactInterface` 是 Player 的惰性 Interface。`generate_artifact()` 与 `generate_node()` 只允许可写 Player，且均为幂等创建操作；前者不会自动创建节点。`refresh_artifact()`、`refresh_node()` 与 `refresh_stale()` 按计算版本更新已有记录，由启动期 reconciliation 调用。每次创建、刷新或移除 Artifact/Node 都递增 PlayerVersion 并清空请求内 `PlayerFileTree` 缓存。`get_tree()` 将静态 `FileTree` 与当前玩家节点合并。

模块先注册 `ArtifactTemplate`，再注册指向它的 `ArtifactNodeTemplate`。模板版本由全部可序列化字段和 callback ID 计算；callback 必须以 `module_handler(module)(revision)` 标记。Artifact 与 Node generator 直接接收 `Player`，不得依赖 Request-ID、followup 或命令拒绝行为。节点运行时可改变 path、display、hidden，但不能改变 stable ID、artifact locator 或计算出的 `version`。Registry 冻结为 `ArtifactCatalog`，其 `TemplateVersion` 汇总全部 Artifact 与 ArtifactNode 模板版本。

旧模块的 generator 若接收 `ArtifactGenerationContext`，应改为直接接收 `Player`，并把 `context.player` 访问替换为该参数。该上下文类型已删除。

## Service 与端点

没有 Artifact 生成 HTTP 端点，也没有 ArtifactService Router。命令 handler 直接调用 `context.player.artifacts.generate_artifact()` 与 `generate_node()`；读取经 FileService：

- `GET /api/v1/files/d/ls`、`/d/tree`、`/d/version` 返回静态与 Artifact 合并树。
- 通用 metadata、content URL、download URL 路由也读取合并树。

Artifact content token 使用 `act2_`，payload 绑定 player ID、ArtifactVersion、ArtifactNodeVersion、对象 key/version、媒体类型和下载名，因而每位玩家的 token 不可互用。

## Example 与限制

Example 注册 `example.admin-access` 和 `/archive/ADMIN_ACCESS.txt` 节点。Guest 验证成功后推进 completed、发放 Administrator 并生成凭据；新的 Request-ID 重复提交不会重新生成。该文件仅在完成谜题且当前登录 Guest 时出现在动态树中。

启动期在 Registry freeze 后运行 `ArtifactReconciliationRunner`。它读取本地 JSON Catalog 快照；TemplateVersion 未变且没有迁移期遗留记录时跳过，变化时仅查询受影响模板拥有者并在命令执行器事务内刷新。同步成功前应用不会 ready。对象上传发生在 SQL 事务提交前，回滚可能留下 `artifacts/` 前缀下的孤儿对象。`ArtifactCleanupService.sweep(session)` 是无 Router、无调度器的最佳努力维护工具。客户端读取规则见 [文件 API](../api/files.md)。

相关实现：`registry/artifacts/`、`players/interfaces/artifacts.py`、`services/artifacts/reconciliation.py`、`services/artifacts/snapshot.py`、`services/artifacts/cleanup.py`。
