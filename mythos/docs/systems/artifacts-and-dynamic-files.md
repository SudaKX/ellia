# Artifact 与动态文件系统

## 持久化与 Model

Artifact 拥有 `player_artifacts` / `PlayerArtifact`、`player_artifact_nodes` / `PlayerArtifactNode` 与 `player_artifact_states` / `PlayerArtifactState`。前两者分别保存已应用的 `ArtifactVersion`、`ArtifactNodeVersion`、对象引用和运行时节点属性；状态表保存玩家独立、单调递增的 `PlayerVersion`。

## Interface、Registry 与数据对象

`ArtifactInterface` 是 Player 的惰性 Interface。`generate_artifact()` 与 `generate_node()` 只允许可写 Player，且均为幂等创建操作；前者不会自动创建节点。`refresh_artifact()`、`refresh_node()` 与 `refresh_stale()` 按计算版本更新已有记录，由启动期 reconciliation 调用。每次创建、刷新或移除 Artifact/Node 都递增 `ArtifactInterface.version`，并通过 Player 注入的 mutation callback 清空 Player 的请求内 `PlayerFileTree` 缓存。`tree_nodes()` 只构造当前玩家实际拥有的 Artifact TreeNode，不复制静态树；请求期由 `MergedFileTree.fruit()` 按 path 映射到 Slot。

模块先注册 `ArtifactTemplate`，再注册指向它的 `ArtifactNodeTemplate`。模板版本由全部可序列化字段和 callback ID 计算，前缀分别为 `atv1_` 与 `antv2_`；Artifact node version 还包含对应的 ArtifactTemplate version，使新的 Artifact meta 可以触发 node generator 重建。callback 必须以 `module_handler(module)(revision)` 标记。Artifact generator 接收 `Player`；Node generator 严格接收 `Player`、Artifact meta 与运行时 node。ArtifactTemplate 提供默认下载名，ArtifactNodeTemplate 和运行时 node 可覆盖该名称。Registry 冻结为 `ArtifactCatalog`，其 `version` 使用 `acv1_` 汇总全部 Artifact 与 ArtifactNode 模板版本。

旧模块的 generator 若接收 `ArtifactGenerationContext`，应改为直接接收 `Player`，并把 `context.player` 访问替换为该参数。该上下文类型已删除。

## Service 与端点

没有 Artifact 生成 HTTP 端点，也没有 ArtifactService Router。命令 handler 直接调用 `context.player.artifacts.generate_artifact()` 与 `generate_node()`；读取经 FileService：

- `GET /api/v1/files/d/ls`、`/d/tree`、`/d/version` 返回静态与 Artifact 合并树。
- 通用 metadata、content URL、download URL 路由也读取合并树。

Artifact content token 使用 `act3_`，payload 绑定 player ID、artifact ID、node ID、ArtifactVersion、ArtifactNodeVersion、媒体类型和最终下载名，因而每位玩家的 token 不可互用。Artifact 对象 key 为 `artifacts/<player_id>/<artifact_version>`；相同玩家和 ArtifactVersion 的 generator 必须生成确定性内容。`node_generator` 返回的 path 必须等于模板 path，否则写入失败。

## Example 与限制

Example 注册 `example.admin-access` 和 `/archive/ADMIN_ACCESS.txt` 节点。Guest 验证成功后推进 completed、发放 Administrator 并生成凭据；新的 Request-ID 重复提交不会重新生成。该文件仅在完成谜题且当前登录 Guest 时出现在动态树中。

启动期在 Registry freeze 后运行 `ArtifactReconciliationRunner`。它读取本地 JSON Catalog 快照；ArtifactCatalog version 未变且没有迁移期遗留记录时跳过，变化时仅查询受影响模板拥有者并在命令执行器事务内刷新。同步成功前应用不会 ready。对象上传发生在 SQL 事务提交前，回滚可能留下 `artifacts/` 前缀下的孤儿对象。`ArtifactCleanupService.sweep(session)` 是无 Router、无调度器的最佳努力维护工具。客户端读取规则见 [文件 API](../api/files.md)。

相关实现：`registry/artifacts/`、`players/interfaces/artifacts.py`、`services/artifacts/reconciliation.py`、`services/artifacts/snapshot.py`、`services/artifacts/cleanup.py`。
