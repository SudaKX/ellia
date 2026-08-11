## 1. 版本与 callback 基础

- [x] 1.1 在 `registry/callbacks.py` 中引入新的固定 UUID namespace，确定 callback ID schema 2 的规范化输入格式、依赖 mask 和稳定序列化规则，并固定测试向量。
- [x] 1.2 扩展 `module_handler`，支持 access_rule 声明 `PlayerInterfaces` 依赖，并区分未指定依赖与显式 `PlayerInterfaces.NONE`。
- [x] 1.3 在 callback 校验和文件注册阶段拒绝未声明或包含非法 bit 的 access_rule 依赖。
- [x] 1.4 增加 `VersionedPlayerInterface` Protocol，统一 Progress、Account、Artifact、Credit Interface 的 `version` 行为，并将 ArtifactInterface 的 `player_version` 统一为 `version`。
- [x] 1.5 在 `Player` 中实现按 `PlayerInterfaces` bitmask 返回稳定状态版本向量的方法，并对未加载或无有效版本的依赖返回明确错误。
- [x] 1.6 为现有 Example、测试注册表和文件 manifest access_rule 补充显式依赖声明，确保无状态规则使用 `PlayerInterfaces.NONE`。
- [x] 1.7 增加 callback ID、依赖 mask、Interface 版本向量的单元测试和固定测试向量。

## 2. MergedFileTree 与 Slot 拓扑

- [x] 2.1 在文件注册表模块中增加最小 `TreeNodeSlot`，使用 `artifact_locator is None` 区分目录 Slot 和文件 Slot，并保存 path、file ID 和 children 拓扑信息；MergedFileTree 拓扑接受 `TreeNode | TreeNodeSlot` 共存，由文件树模块集中处理运行时类型判断，不引入共享运行时基类。
- [x] 2.2 实现启动期将静态 FileTree 与 ArtifactNodeTemplate path 物理插入为 `MergedFileTree` 的构建流程，补全共享祖先目录 Slot。
- [x] 2.3 在 MergedFileTree 构建阶段增加静态路径、动态文件 Slot、目录 Slot 之间的冲突检测。
- [x] 2.4 实现 `MergedFileTree.resource_version` 的 `mft1_` 指纹，payload 仅包含 schema、静态 FileTree version 和 Artifact Catalog version。
- [x] 2.5 将 MergedFileTree 接入 RuntimeCatalogs、应用装配和 FileService，保留静态 FileTree 给静态文件端点使用。
- [x] 2.6 增加 MergedFileTree 的 Slot、共享祖先、路径冲突和资源版本传播测试。

## 3. Artifact path 约束与 Fruiting

- [x] 3.1 修改 Artifact node materialization 校验，禁止 node_generator 修改 path，并保留 stable_id、artifact_locator、version 的身份校验。
- [x] 3.2 更新 Artifact reconciliation 和历史记录处理，使已有 path 不一致的 PlayerArtifactNode 在应用 ready 前得到修复或阻止启动。
- [x] 3.3 将 ArtifactInterface 的动态节点构造改为提供当前玩家实际 Artifact TreeNode 数据，不再构造完整静态树副本。
- [x] 3.4 实现 `MergedFileTree.fruit()`，以实际 ArtifactNode path 构建 `nodes_by_path`，并为每个 Artifact 文件补全祖先目录 TreeNode 映射。
- [x] 3.5 实现 PlayerFileTree 对 MergedFileTree 的引用关系，禁止 fruiting 修改共享 MergedFileTree 拓扑。
- [x] 3.6 在 PlayerFileTree 查询中实现 TreeNodeSlot path resolve；无映射 Slot 在目录枚举和递归树中跳过，文件查找返回未找到。
- [x] 3.7 保持现有 hidden、路径链 access_rule、403/404 和 content-token 校验行为，并增加已拥有但无权访问节点的回归测试。
- [x] 3.8 增加未拥有节点、共享祖先、Artifact 文件和动态前置目录的 fruiting 与多玩家隔离测试。

## 4. Player 缓存与动态版本

- [x] 4.1 将完整 PlayerFileTree 请求缓存从 ArtifactInterface 移到 Player，并提供 `Player.invalidate_cache()`。
- [x] 4.2 在 Player 加载 Interface 时注入统一 mutation callback，使进度、账号、Artifact、credits 等成功写入路径自动调用 `invalidate_cache()`。
- [x] 4.3 更新 `FileIdCodec.encode_player_tree_version()`，生成 `pft4_`，组合 MergedFileTree resource version、ArtifactInterface.version 和 access_rule 依赖所需的状态版本。
- [x] 4.4 修改 FileService 动态树、目录、metadata 和 content URL 流程，使其消费引用 MergedFileTree 的 PlayerFileTree。
- [x] 4.5 修改 `/files/d/version`、动态列表、动态树和 metadata 的版本测试，验证账号或进度变化后旧 ETag 不返回 304，状态不变时仍返回 304。
- [x] 4.6 增加无关 credits 状态变化不改变 pft4_ 的测试，并验证 Artifact 状态变化仍然使 pft4_ 失效。
- [x] 4.7 审查 Example 前端动态刷新逻辑，使 `/files/d/version` 成为进度和账号变化后的主要刷新依据，删除不再需要的重复状态判断或保留明确的防御性行为。

## 5. 文档与协议迁移

- [x] 5.1 更新版本架构文档，记录资源版本、状态版本、`mft1_`、`pft4_` 和 callback 依赖传播链。
- [x] 5.2 更新启动注册、文件系统、Artifact、Player Context 和 API 缓存文档，说明 MergedFileTree、TreeNodeSlot、path fruiting 和 `invalidate_cache()`。
- [x] 5.3 更新 API 与 Example 流程文档，说明动态 ETag 覆盖 access_rule 相关状态变化，保持 HTTP 路径和响应结构说明一致。
- [x] 5.4 明确 Hint disclosure 没有状态版本时不能作为文件 access_rule 依赖，并记录未来增加 Hint revision 的边界。
- [x] 5.5 完成实现和测试后移除 `docs/TODO.md` 中的动态 PlayerFileTree 版本条目。

## 6. 综合验证

- [x] 6.1 扩展动态文件集成测试，覆盖注册、Artifact fruiting、Slot resolve、账号切换、进度推进、旧 ETag 和 304 条件。
- [x] 6.2 扩展 Example 端到端测试，验证 Guest、Administrator 和 Artifact 文件在不同状态版本下的可见性与 tree_version。
- [x] 6.3 从 `mythos/` 目录运行聚焦测试，覆盖动态文件、Example、注册表、Player、Artifact 和状态 Interface。
- [x] 6.4 从 `mythos/` 目录运行完整测试目录，确认现有静态文件、对象存储、Hint、Credits、认证和迁移测试不回归。
