## Context

当前静态文件由 `FileTree` 在启动期构建，Artifact 节点由 `ArtifactInterface.get_tree()` 在请求期从玩家记录组装。现有实现会深复制静态树，再把当前玩家的 Artifact 节点插入副本；完整树缓存位于 `ArtifactInterface`，其失效主要由 Artifact 写入路径负责。

动态文件的可见性还依赖 `Player` 上的 `access_rule`。Example 当前规则读取 `accounts` 和 `progress`，但 `pft3_` 只包含静态 FileTree 版本、Artifact Catalog 版本和 `PlayerArtifactState.version`。因此账号切换或进度变化可能改变可见文件，却不会改变 `/files/d/version` 的 ETag。

本设计受以下约束：

- Registry 在启动期冻结，`MergedFileTree` 只在启动期构建。
- Service 是全局对象，只消费冻结 Catalog 和请求级 Player。
- 玩家写入必须通过现有命令事务和 Player Interface。
- 文件 API 路径、响应结构、访问错误语义和 content-token 语义保持不变。
- `MergedFileTree` 只读是架构约定，不增加代码级不可变包装或运行时冻结机制。

## Goals / Non-Goals

**Goals:**

- 建立 `资源版本 -> Catalog -> MergedFileTree` 的资源版本链。
- 建立 `数据库状态版本 -> PlayerInterface -> Player -> PlayerFileTree` 的状态版本链。
- 启动期将静态文件节点和 ArtifactNodeTemplate 的 Slot 合并为共享的 `MergedFileTree`。
- 请求期只保存玩家 ArtifactNode 的实际数据映射，不复制整个合并树。
- 通过显式 access_rule 依赖生成稳定 callback ID，并复用现有资源版本传播链。
- 通过统一的 Interface version Protocol 生成 `pft4_`。
- 通过 `Player.invalidate_cache()` 管理请求级文件树缓存。
- 保留动态文件的 hidden 和 access_rule 查询语义。

**Non-Goals:**

- 不引入独立的 `VisibilityProjection` 类型；可见性计算直接由 `PlayerFileTree` 查询完成。
- 不改变静态文件 ID、Hint ID、Artifact content-token 或对象存储 key 的协议。
- 不允许 node generator 修改节点 path，但本 change 不重新设计其他 node generator 字段。
- 不为 `pft4_` 增加数据库列或数据库迁移。
- 不让 Hint disclosure 状态自动成为文件 access_rule 依赖；若未来需要，必须先增加独立状态版本设计。
- 不通过 Python 字节码或运行时反射自动推断 access_rule 依赖。

## Decisions

### 1. 使用 `MergedFileTree` 作为共享静态合并拓扑

`MergedFileTree` 是启动期运行时静态容器，包含静态文件拓扑、Artifact Slot、Slot 索引和资源版本。名称不使用 `Template`，避免与 `ArtifactTemplate`、`ArtifactNodeTemplate` 的注册期语义混淆。

`MergedFileTree.resource_version` 使用 `mft1_`，payload 只包含：

```text
schema: 1
static_tree_version: fcv1_
artifact_catalog_version: acv1_
```

Slot 布局来自静态 FileTree 和 Artifact Catalog，因此不重复写入 mft payload。access_rule 依赖声明会进入 callback ID，callback ID 已参与 StaticNode version 和 ArtifactNode version，最终会传播到 `fcv1_` 或 `acv1_`。

选择该方案而不是在 `mft1_` 中重复列出所有 Slot 的原因是避免三处维护同一版本输入。若 Slot 构建算法本身发生不兼容变化，只递增 `mft` schema。

### 2. 用最小的 `TreeNodeSlot` 表示动态占位

MergedFileTree 的拓扑允许普通 `TreeNode` 和 `TreeNodeSlot` 两种节点。Slot 只保存查询和拓扑所需的信息：

```text
path
artifact_locator: str | None
file_id: str | None
children
```

`artifact_locator` 非空表示 Artifact 文件 Slot，为空表示 Artifact 前置目录 Slot。目录 Slot 不拥有 public file ID。

`path` 是请求期玩家节点映射的查询键。由于 node generator 不再允许修改 path，路径在注册期、持久化记录和请求期 fruiting 之间保持一致。

`TreeNodeSlot` 不继承 `TreeNode`，也不与 `TreeNode` 共享要求完整 definition/content 的运行时基类。`TreeNode` 表示已经解析的实际节点，`TreeNodeSlot` 表示尚未解析的占位节点，两者生命周期和可访问字段不同。MergedFileTree 内部使用 `TreeNode | TreeNodeSlot` 联合拓扑；文件树模块提供一个集中式 Slot-aware 遍历/resolve 辅助函数，在遇到 Slot 时使用 path 查询 PlayerFileTree 映射。除这个边界外，现有 TreeNode 查询逻辑保持不变。

启动期对每个 ArtifactNodeTemplate 的 path 做物理插入：缺失的祖先目录创建目录 Slot，叶节点创建文件 Slot。共享祖先只创建一次。静态文件、静态目录、文件 Slot 和目录 Slot 的路径冲突在启动期拒绝。

### 3. PlayerFileTree 引用 MergedFileTree，不复制共享拓扑

PlayerFileTree 保存：

```text
merged_tree: MergedFileTree
nodes_by_path: Mapping[str, TreeNode]
tree_version: pft4_
```

`nodes_by_path` 只保存当前玩家实际拥有的 Artifact 文件节点和其祖先目录节点。祖先目录使用当前隐式目录语义：没有 definition、没有 content、没有子节点；子节点拓扑仍由 MergedFileTree 提供。

Fruiting 流程为：

1. 根据玩家 `PlayerArtifactNode` 和当前 `ArtifactNodeTemplate` 构造实际可用的 Artifact TreeNode。
2. 以实际节点 path 写入 `nodes_by_path`。
3. 对每个实际节点的所有祖先 path 写入目录 TreeNode，重复祖先只保留一个映射。
4. 不复制或修改 `MergedFileTree`。

Fruiting 假设持久化边界和启动 reconciliation 已保证节点有效，不在请求期重复做业务校验。无法通过 path 找到对应 Slot 的异常节点不加入映射，也不阻断其他文件读取。

查询 `MergedFileTree` 时遇到 `TreeNodeSlot`，直接以 `slot.path` 查询 `nodes_by_path`：

- 有映射目标时使用实际 TreeNode。
- 无映射目标时视为不可用；目录枚举和递归树跳过，文件查找返回未找到。
- 已 resolve 的节点继续执行现有 hidden 和 access_rule 逻辑。

Artifact 文件被拥有但 access_rule 拒绝时，祖先目录仍可根据当前行为存在，叶节点在访问过滤阶段被排除。

### 4. 禁止 node generator 修改 path

`node_generator` 返回的 path 必须等于 `ArtifactNodeTemplate.path`。stable ID、artifact locator、version 和 path 都是不可修改身份字段；display、hidden 和 download_name 仍允许按现有规则生成运行时值。

固定 path 使 Slot 可以使用 path 作为稳定查询键，也使 MergedFileTree 的物理拓扑不依赖玩家数据。历史记录中的不一致 path 由启动 reconciliation 修复；请求期 fruiting 不负责修复。

### 5. 用 Protocol 统一 PlayerInterface 版本行为

增加结构化类型协议：

```python
class VersionedPlayerInterface(Protocol):
    @property
    def version(self) -> int:
        ...
```

当前 Progress、Account、Artifact 和 Credit Interface 实现该协议。ArtifactInterface 的 `player_version` 统一为 `version`。HintInterface 在未拥有可用状态版本前不能作为文件 access_rule 依赖；未来若开放该依赖，需要增加玩家 Hint 状态 revision。

Player 集中提供按 `PlayerInterfaces` bitmask 获取版本向量的方法。Service 不直接拼接各个 Interface 的属性，避免版本字段和 Interface 映射散落在多个调用点。

### 6. access_rule 依赖进入 callback ID

扩展现有 module handler，使 access_rule 可以声明 Interface 依赖：

```python
@handler(1, dependencies=PlayerInterfaces.ACCOUNTS)
def access_rule(player: Player) -> bool:
    ...
```

不读取玩家状态的规则显式声明 `PlayerInterfaces.NONE`；使用玩家状态但未声明依赖的规则在注册或 freeze 阶段失败。

callback ID 的稳定输入增加规范化依赖 mask，并升级 callback ID schema 或 namespace：

```text
callback-schema
module
qualname
revision
dependencies
```

本 change 使用新的固定 UUID namespace 生成 callback ID。新 namespace 必须是源码中的稳定常量，不能在进程启动或调用时随机生成；旧 namespace 继续保留在历史实现中，不与新 callback ID 混用。

这样依赖变化会自动触发：

```text
callback_id
  -> StaticNode.version / ArtifactNode.version
  -> FileCatalog.version / ArtifactCatalog.version
  -> MergedFileTree.resource_version
```

不额外把依赖 mask 手工加入 StaticNode 或 ArtifactNode 的版本 payload。

未指定依赖和 `NONE` 必须区分。生成器等非 access_rule callback 可以没有依赖元数据，但所有被注册为文件访问规则的 callback 必须完成声明。

### 7. 动态版本由资源版本和状态版本合成

PlayerFileTree 的 public tree version 升级为 `pft4_`：

```json
{
  "schema": 4,
  "merged_file_tree_version": "mft1_...",
  "state_versions": {
    "artifacts": 3,
    "accounts": 4,
    "progress": 5
  }
}
```

状态版本只包含 MergedFileTree access_rule 依赖所需的 Interface，再加上 Artifact fruiting 所需的 ArtifactInterface。未声明的 credits 或 hints 状态不会导致动态树版本无条件变化。

`FileIdCodec.encode_player_tree_version()` 在本 change 中消费新的 payload，保留现有 API 端点和 ETag 生成方式。未来可以将通用动态版本合成抽取到独立 VersionCodec，但本 change 不要求拆分现有 FileIdCodec。

### 8. 请求缓存使用显式失效

完整 PlayerFileTree 的缓存从 ArtifactInterface 移到 Player。Player 提供：

```text
invalidate_cache()
get_file_tree(...)
```

所有会改变玩家状态的 Interface 写入方法在成功修改后调用 Player 注入的失效回调。请求缓存不使用资源/状态版本向量作为 key；版本向量只用于生成 public `pft4_`。

ArtifactInterface 不再负责完整 PlayerFileTree 的缓存，只负责当前玩家 Artifact 数据和实际节点构造。

### 9. 查询阶段不引入 VisibilityProjection 类型

PlayerFileTree 直接实现动态树查询和可见性过滤。其查询流程为：

```text
MergedFileTree 拓扑遍历
  -> TreeNodeSlot path resolve
  -> hidden 过滤
  -> access_rule 过滤
  -> DirectoryListing / DirectoryTree / metadata
```

`/files/d/version` 只计算资源版本和状态版本，不执行 access_rule。其他动态文件读取路径继续在每次请求中重新执行 access_rule，tree version 不替代授权检查。

## Risks / Trade-offs

- [依赖声明遗漏] callback 可能实际读取未声明的 Player 状态，造成 ETag 不失效。→ freeze 阶段拒绝未声明 access_rule；增加测试期规则依赖审计和跨状态 ETag 测试。
- [共享树被意外修改] MergedFileTree 依靠规范而非代码冻结，任何写操作都可能污染其他请求。→ 限制修改入口只在启动构建阶段；PlayerFileTree 只写自己的 path 映射；增加多玩家隔离测试。
- [Slot 目录残留] 物理拓扑包含所有可能的动态目录，未拥有节点时可能暴露空目录。→ 目录 Slot 必须通过 path 映射 resolve；无映射目录 Slot 在枚举时跳过；静态目录和动态目录来源需要区分。
- [持久化数据异常] 旧 ArtifactNode path 或 template 关系不一致时，path 映射可能丢弃节点。→ 启动 reconciliation 负责修复；请求期 fruiting 采用容错跳过，不阻断其他文件。
- [callback ID 一次性变化] 依赖进入 callback ID 后会导致现有资源版本整体刷新。→ 将 callback schema/namespace 作为明确协议升级；旧 ETag 和旧 Catalog 版本只作为自然失效处理。
- [缓存失效遗漏] 新增 Interface 写路径若不调用 invalidate_cache，会在同一请求内复用旧树。→ 由 Player 加载 Interface 时注入统一 mutation callback，并为每个写方法增加测试。
- [全局依赖过度失效] 使用 `ALL` 会导致无关状态改变时刷新文件树。→ 版本向量只采集已声明依赖；请求加载可以暂时使用 ALL，但不把 ALL 作为版本输入。
- [Hint 没有状态版本] Hint disclosure 不能安全地成为文件 access_rule 依赖。→ 当前明确排除；未来先增加独立 Hint state revision，再开放依赖位。

## Migration Plan

1. 先实现并测试 callback ID 新 schema、依赖声明和资源版本传播。
2. 在启动期构建 MergedFileTree，校验静态节点与 Artifact Slot 的路径冲突。
3. 在请求期切换到 path 映射 fruiting 和 Player 持有的请求缓存。
4. 切换 `pft3_` 到 `pft4_`，更新动态文件 HTTP 测试和客户端使用说明。
5. 更新 Example 的 node generator 和已有测试数据，使 path 只读。
6. 更新版本架构、文件系统、Artifact、Player Context、API 缓存文档，完成后移除 TODO 条目。

本 change 不新增数据库迁移。已有 `PlayerProgress.version`、`PlayerVirtualAccountState.version`、`PlayerArtifactState.version` 和 `PlayerCredits.version` 继续作为状态来源。旧 `pft3_` ETag 因 prefix/schema 改变自然失效。

如果启动 reconciliation 发现历史 ArtifactNode path 不一致，应在应用进入 ready 前修复；无法修复时保持启动失败，不让错误数据进入新的 MergedFileTree 查询路径。

回滚时需要同时回滚应用代码和资源版本协议。由于 `pft4_` 只存在于运行时响应，不需要数据库回滚；回滚到旧代码后旧客户端会重新获得 `pft3_`，但必须确保旧版本仍能读取已有 Artifact 数据。

## Open Questions

- callback ID 的新 schema 使用新的固定 UUID namespace；实现时需要固定 namespace 常量和 callback ID 测试向量。
- MergedFileTree 的内部拓扑接受 `TreeNode` 与 `TreeNodeSlot` 两种类型共存。`TreeNodeSlot` 不继承 `TreeNode`，也不引入共享运行时基类；文件树模块只在拓扑遍历和 Slot resolve 边界使用一次 `isinstance` 或等价类型判断。这样可以保持 Slot 的最小字段集合，并避免现有 TreeNode 的 `definition`、`content` 和 `is_file` 语义被占位节点污染。
- 若未来允许 `HintInterface` 参与文件 access_rule，需单独设计 Hint 状态版本表和迁移，不在本 change 内扩大范围。
