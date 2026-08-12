## Why

当前动态文件树把静态文件、玩家 Artifact 节点和访问授权状态混在一次请求级构建中。`PlayerFileTree` 版本只覆盖静态 FileTree、Artifact Catalog 和 Artifact 状态，未覆盖 `progress`、`accounts` 等会改变 `access_rule` 结果的玩家状态，导致 `GET /files/d/version` 可能错误返回旧 ETag 或 `304`，客户端继续使用过期的可见文件树。

同时，现有动态树每次从静态树深复制并重新插入 Artifact 节点，无法清晰表达启动期静态拓扑、Artifact Slot 和请求期玩家数据之间的边界。需要建立可复用的资源版本、状态版本和动态文件树构建模型。

## What Changes

- 新增启动期 `MergedFileTree`，将静态文件树与 Artifact 文件、前置目录的 `TreeNodeSlot` 拓扑合并。
- 将实际玩家 `ArtifactNode` 通过 path 映射 fruiting 到 Slot，不再复制整个共享合并树。
- 禁止 `node_generator` 修改 Artifact 节点 path，使 Slot 路径和请求期映射稳定。
- 抽象资源版本链：注册表项、Catalog 和 `MergedFileTree` 资源版本逐级传播。
- 抽象状态版本链：数据库状态、PlayerInterface、Player 和动态文件树版本逐级传播。
- 为所有可作为文件 `access_rule` 依赖的 PlayerInterface 提供统一的版本 Protocol。
- 通过现有 callback 装饰器声明 access_rule 依赖，并将依赖信息纳入 callback ID，从而复用现有 StaticNode、ArtifactNode 和 Catalog 版本链。
- 将动态树版本升级为 `pft4_`，由 `MergedFileTree` 资源版本与请求所需的玩家状态版本向量组成。
- 将请求缓存失效统一为 `Player.invalidate_cache()`，由状态修改路径自动触发。
- 保持现有文件 API 路径、响应结构、访问校验和 content-token 语义不变；动态 ETag 的实际失效范围将扩大。
- 更新动态文件、版本、Artifact、Player Interface、缓存和架构文档，并补充跨状态版本和 Slot fruiting 回归测试。

## Capabilities

### New Capabilities

- `merged-file-tree-versioning`: 定义静态资源版本、玩家状态版本、MergedFileTree、TreeNodeSlot、Fruiting、动态 `pft4_` 版本以及相关 HTTP 缓存行为。

### Modified Capabilities

- 无

## Impact

- 后端注册表与运行时容器：`registry/files`、`registry/artifacts`、`registry/bundle.py`。
- 玩家状态与请求缓存：`players/player.py`、Player Interfaces、`PlayerFactory` 和命令写入路径。
- 文件服务：`services/files/service.py`、`services/files/router.py` 以及动态目录、树、metadata 和 URL 授权流程。
- 版本编码：`core/file_ids.py`、callback ID 和现有资源 Catalog 版本实现。
- 持久化：不需要为 `pft4_` 增加迁移；若为 Hint 状态开放文件访问依赖，需另行设计其状态版本表。
- 测试与文档：动态文件、Example 流程、版本架构、缓存说明和 TODO。
