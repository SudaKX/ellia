# 启动、注册表与 Artifact 流程

本文按当前 `src/mythos/` 实现说明四条链路：

1. 后端从 `create_app()` 到应用 ready 的启动阶段。
2. Registry 中声明对象的注册、物化和 freeze 顺序。
3. Version、Catalog version、File ID 和 content-token 的依赖与生成时机。
4. Artifact 在启动 reconciliation、写入请求和读取请求中的完整顺序。

本文中的“注册期”是模块向 Registry 写入声明的阶段；“冻结期”是声明被解析为运行时 Catalog 的阶段；“请求期”是 Player Interface 在 HTTP 请求或命令事务中加载、生成和持久化玩家数据的阶段。

## 一、启动阶段

当前启动主链路如下：

```text
create_app()
  -> 读取运行根目录 Settings
  -> 从 Settings.puzzle_root 加载外部 puzzles.register_all(registries, environment)
  -> 创建 RegistryBundle 并注册插件内容
  -> FastAPI 路由装配

lifespan startup
  -> FileIdCodec、ObjectStore、Database
  -> StaticAssetPublisher 物化 Files/Hints 静态源
  -> RegistryBundle.freeze(file_ids)
  -> PlayerLoader、checkpoint hook、EndpointCommandExecutor、TaskCommandExecutor、LifecycleDispatcher
  -> ArtifactReconciliationRunner
  -> AccountReconciliationRunner
  -> ApplicationRuntime 挂载到 app.state.runtime
  -> yield，应用 ready
```

### 1. `create_app()` 与模块注册

`create_app()` 的同步装配阶段位于应用 lifespan 之前：

1. 解析 `Settings`。
2. 如果调用方没有传入 RegistryBundle，则创建 `RegistryBundle(settings.puzzle_root)`。
3. 将 `Settings.puzzle_root` 的上级目录加入 `sys.path`，通过 `importlib` 加载固定名称 `puzzles`。
4. 校验外部包位置及 `register_all(registries, *, environment)` 入口。
5. 调用 `register_all()`，由插件显式注册各谜题模块。
6. 再次确认 Registry 使用当前 `puzzle_root`。
7. 创建 FastAPI、异常处理器和固定 Router。

此时只存在内存中的注册声明，不创建数据库 Session，也不生成 `ApplicationRuntime`。模块只能向既有 Registry 注册内容和 callback，不能新增通用 HTTP Router。

当前 Example 模块的注册调用顺序是：

```text
Progress nodes
  -> File tree manifest and static FileReference/StaticNodeSpec
  -> Hint definitions and Hint sources
  -> VirtualAccountTemplate
  -> Construct lifecycle handler
  -> ArtifactTemplate
  -> ArtifactNodeTemplate
  -> Script
  -> ValidationAttempt
```

跨 Registry 的注册顺序由模块代码决定；RegistryBundle 不要求模块必须按照上述顺序注册。但 ArtifactNodeTemplate 必须指向已经注册的 ArtifactTemplate，当前 `ArtifactRegistry.register_node()` 会立即检查这一点。

### 2. lifespan 基础设施

进入 lifespan startup 后按以下顺序创建基础设施：

1. `FileIdCodec(settings.file_id_secret)`：负责 `f1_`、`h1_` 和 File ID key fingerprint。
2. `ObjectStore`：使用注入的对象存储，或由 Settings 创建 RustFS/S3 client。
3. `Database`：创建 AsyncEngine 和 Session factory。

数据库 migration 不在 `create_app()` 内自动执行。生产环境应在启动前从 `mythos/` 执行 Alembic migration。

### 3. 静态源物化

`RegistryBundle.materialize_static_files()` 将 Files Registry 和 Hint Registry 的 `FileReference` 按 `module:relative_path` 合并，然后调用 `StaticAssetPublisher.materialize()`：

1. 读取每个 source 的完整字节。
2. 计算 `sha256:<64 位小写 hex>`。
3. 如果 `StaticFileRegistration` 中的摘要和 media type 均一致，则复用登记的 `ObjectReference`。
4. 否则写入固定 key：`static/{module}/{relative_path}`。
5. 在 SQL 事务中更新或创建 `StaticFileRegistration`。
6. 将 Files 自己引用的对象分配给 `FileRegistry`。
7. 将 Hints 自己引用的对象分配给 `HintRegistry`。

静态源必须在 Registry freeze 前完成物化。此阶段只生成对象引用和发布登记，不生成 FileTree 的最终 node version；最终 `snv1_` 要等到 freeze 时把对象引用和节点声明合并后才能计算。

### 4. Registry freeze

`RegistryBundle.freeze(file_ids)` 首先检查静态 File node 与 Artifact node 的 `stable_id` 不冲突，然后按代码中的固定顺序冻结：

```text
files       -> FileTree
artifacts   -> ArtifactCatalog
merged file -> MergedFileTree (mft1_)
progress    -> ProgressGraph
scripts     -> ScriptCatalog
validations -> ValidationCatalog
accounts    -> VirtualAccountCatalog
hints       -> HintCatalog
lifecycle   -> LifecycleCatalog
```

返回的 `RuntimeCatalogs` 是应用运行期使用的 Catalog 集合。Registry 在 freeze 后拒绝继续注册；Catalog 中的映射由构造时复制，运行期不再接受新的注册项。

### 5. 运行时对象和启动 reconciliation

Registry freeze 后继续创建：

1. `PlayerLoader`：把 RuntimeCatalogs、ObjectStore 和 FileIdCodec 组合为 Player loader。
2. `LocalCheckpointStore` 和 `ProgressCheckpointHook`。
3. `EndpointCommandExecutor`、`TaskCommandExecutor` 和 Request-ID cache。
4. `PlayerLifecycleDispatcher`。

然后按顺序执行：

1. `ArtifactReconciliationRunner`：根据 Artifact Catalog 快照刷新玩家 Artifact/Node。
2. `AccountReconciliationRunner`：根据 VirtualAccount Catalog 快照清理已退休账号类型。

两个 reconciliation 成功后才写入对应的本地 Catalog snapshot。任何 reconciliation 异常都会阻止 lifespan 进入 `yield`。

最后创建 `ServiceContainer`，把静态 FileTree、启动期共享的 MergedFileTree、HintCatalog、ProgressGraph、ScriptCatalog、ValidationCatalog 和对象存储等注入全局 Service，并将完整 `ApplicationRuntime` 保存到 `app.state.runtime`。

应用退出时，lifespan 的 `finally` 释放 Database。Catalog、Service 和 PlayerLoader 的生命周期属于当前应用进程。

## 二、Registry 数据模型初始化顺序

### 1. RegistryBundle 中的八个 Registry

`RegistryBundle.__init__()` 创建以下空 Registry：

| 顺序 | Registry | 注册数据模型 | freeze 输出 |
| --- | --- | --- | --- |
| 1 | `files` | `FileReference`、`StaticNodeSpec` | `FileTree` |
| 2 | `progress` | `NormalProgressNode`、`BranchProgressNode`、`MergeProgressNode` | `ProgressGraph` |
| 3 | `scripts` | `Script` | `ScriptCatalog` |
| 4 | `validations` | `ValidationAttempt` | `ValidationCatalog` |
| 5 | `artifacts` | `ArtifactTemplate`、`ArtifactNodeTemplate` | `ArtifactCatalog` |
| 6 | `accounts` | `VirtualAccountTemplate` | `VirtualAccountCatalog` |
| 7 | `hints` | `Hint`、Hint source | `HintCatalog` |
| 8 | `lifecycle` | lifecycle handler、event、priority、registration sequence | `LifecycleCatalog` |

Registry 的字段填写顺序是“先完成注册声明，再完成 freeze 期解析”。注册期声明不会提前填写由对象内容、Catalog 或玩家状态决定的运行时版本。

### 2. Files：FileReference -> StaticNodeSpec -> StaticNode -> FileContent -> FileTree

#### 2.1 `FileReference`

注册源时填写：

```text
module
relative_path
media_type
```

`source_locator` 是只读派生值：

```text
{module}:{relative_path}
```

一个 source locator 只能对应一个 FileReference。`module` 必须是单一路径段，`relative_path` 必须是 canonical module-relative path。

#### 2.2 `StaticNodeSpec`

注册期填写：

```text
stable_id
path
display
access_rule
hidden
download_name       # file spec 使用
source_locator      # file spec 使用
```

`StaticNodeSpec` 是 frozen 声明，不填写最终 `version`。`FileRegistry.register_node()` 将它转换为可变的运行时 `StaticNode`，此时版本暂时为空字符串，只用于完成路径、权限、下载名和 source binding 校验。

#### 2.3 freeze 期解析

`FileRegistry.freeze()` 对每个注册 node：

1. 找到对应的 `ObjectReference`。
2. 调用 `static_node_version()`，生成 `snv1_`。
3. 创建最终运行时 `StaticNode`，字段为 stable ID、path、`snv1_`、display、access rule、hidden、download name 和 source locator。
4. 对 file node 创建 `FileContent`：

```text
object_ref       = 物化得到的 ObjectReference
download_name    = StaticNode.download_name
content_token    = StaticNode.version
```

5. `FileTree.build()` 为 file node 生成 `f1_` File ID。
6. `FileCatalog.build()` 对 `(stable_id, StaticNode.version)` 排序，并连同 File ID key fingerprint 生成 `fcv1_`。
7. `FileTree.tree_version` 直接使用该 `fcv1_`。

### 3. Hints：Hint -> HintCatalog

注册 `Hint` 时填写：

```text
stable_id
source: FileReference
download_name
display
vtb_cost
access_rule
```

静态物化阶段先为 Hint source 得到 `ObjectReference`。`HintRegistry.freeze()` 随后按以下顺序生成：

1. `h1_` Hint public ID。
2. `hint_version()` 的 `hv1_`，输入 stable ID、source locator、source digest、media type、download name、display、VTB cost 和 access callback ID。
3. `HintCatalog.version` 的 `hcv1_`，输入排序后的 `(stable_id, hv1_)`。
4. `FileContent`，其 `content_token` 直接使用 `hv1_`。

### 4. Artifact：ArtifactTemplate -> ArtifactCatalog

#### 4.1 `ArtifactTemplate`

注册期填写：

```text
artifact_id
media_type
download_name
generator
```

callback 必须有 `module_handler(module)(revision)` 生成的 callback ID。`ArtifactTemplate.version` 在访问时计算为 `atv1_`，输入上述声明字段和 generator callback ID。

#### 4.2 `ArtifactNodeTemplate`

注册期填写：

```text
stable_id
path
display
artifact_locator
node_generator
access_rule
hidden
download_name
```

它本身不持有 Catalog 上下文，因此不独立计算最终 node version。`ArtifactCatalog` freeze 时按 `artifact_locator` 找到对应 `ArtifactTemplate`，调用：

```text
ArtifactNodeTemplate.version_for(ArtifactTemplate.version)
```

得到 effective `antv2_`。`antv2_` 的输入包括 node 声明字段、node/access callback ID 和对应的 `ArtifactTemplate.version`。

#### 4.3 `ArtifactCatalog`

`ArtifactCatalog` 初始化字段的顺序是：

1. 复制 ArtifactTemplate 映射。
2. 复制 ArtifactNodeTemplate 映射。
3. 为每个 node 计算并保存 `_node_versions[node_id]`。
4. 创建 snapshot entries：Artifact entry 使用 `atv1_`，Artifact node entry 使用 effective `antv2_`。
5. 对全部 entry 按 `(kind, template_id)` 排序，生成 `acv1_`。

`ArtifactCatalog.node_version(node_id)` 是运行期获取 Artifact node canonical version 的唯一入口。

### 5. 其他 Registry

#### Progress

`ProgressRegistry.register()` 先保存声明并校验 node 类型、ID、边、entry 和 checkpoint flags。freeze 时 `ProgressGraph.build()` 按 string ID 排序，依次：

1. 为每个 string ID 派生稳定整数 node ID。
2. 构建 successor 和 predecessor 映射。
3. 检查边、节点度数、DAG、entry 和可达性。
4. 计算 `structure_hash`。

Progress branch selector 不参与当前 Content-token 体系。

#### Scripts

`Script` 按以下字段注册：

```text
stable_id
revision
body
access_rule
```

`ScriptCatalog` 只复制映射；读取脚本列表时才执行 access rule。Script revision 是脚本 API 字段，不是当前 `atv1_/antv2_` Catalog version。

#### Validations

`ValidationAttempt` 按以下字段注册：

```text
stable_id
validation_id
handler
```

Registry 校验 ID 唯一性和 slug 格式，freeze 后 `ValidationCatalog` 按 validation ID 查询 handler。handler 在验证命令请求中调用，不在启动 freeze 时执行。

#### VirtualAccount

`VirtualAccountTemplate` 按以下字段注册：

```text
account_id
display_name
permission
metadata
```

构造时先校验 metadata 可 JSON 序列化，再复制为只读映射。`version` 使用 `vat1_`；Catalog snapshot 按 entry 生成 `vac1_`。

#### Lifecycle

注册 lifecycle handler 时填写：

```text
event
handler
priority
registration sequence
```

freeze 时按 `(priority, registration sequence)` 排序，形成 Construct 和 Deconstruct listener tuple。handler 不在 freeze 时执行。

## 三、Version、Catalog Version 与 Content-token

### 1. 总依赖图

```text
module_handler(module)(revision)
  -> callback_id
      -> ArtifactTemplate.version: atv1_
          -> ArtifactCatalog.node_version: antv2_  (linked Artifact node)
               -> ArtifactCatalog.version: acv1_
                   -> MergedFileTree.resource_version: mft1_
                       -> PlayerFileTree.tree_version: pft4_

access_rule dependencies
  -> callback ID schema 2
      -> StaticNode/ArtifactNode version and Catalog version
          -> MergedFileTree.resource_version: mft1_

static source bytes
  -> ObjectReference.content_digest
      -> StaticNode.version: snv1_
          -> FileCatalog.version / FileTree.tree_version: fcv1_
          -> Static File content_token = snv1_
      -> Hint.version: hv1_
          -> HintCatalog.version: hcv1_
          -> Hint content_token = hv1

FileIdCodec signing key
  -> key_fingerprint
      -> FileCatalog.version: fcv1_
  -> stable_id
      -> File ID: f1_ / h1_

PlayerInterface.version vector
  -> PlayerFileTree.tree_version: pft4_

PlayerArtifact.version + PlayerArtifactNode.version
  -> Artifact content_token: act3_
```

### 2. 版本生成顺序

1. 注册 callback 时确定 module、qualname 和 revision；首次访问版本属性时计算 callback ID。
2. 静态 source 在启动物化阶段计算字节摘要。
3. Files freeze 生成 `snv1_`、静态 File ID、`fcv1_`。
4. Hints freeze 生成 `hv1_`、Hint File ID、`hcv1_`。
5. Artifact Catalog freeze 生成 `atv1_`，再用关联 Artifact version 生成 `antv2_`，最后生成 `acv1_`。
6. Registry freeze 使用静态 FileTree 和 Artifact Catalog 构建 MergedFileTree，生成 `mft1_`。
7. Player 第一次请求动态文件时以 path fruiting 生成 `pft4_`。
8. ArtifactInterface 构建动态 TreeNode 时生成 `act3_`。

### 3. 各版本和 token 的输入

| 标识 | 生成时机 | 主要输入 | 用途 |
| --- | --- | --- | --- |
| `f1_` | FileTree freeze / dynamic tree build | stable ID + File ID signing key | 稳定文件定位 |
| `h1_` | HintCatalog freeze | Hint stable ID + File ID signing key | Hint 文件定位 |
| `snv1_` | FileTree freeze | Static node 声明、source digest、media type、display、download name、access callback ID | 静态文件内容 token |
| `hv1_` | HintCatalog freeze | Hint 声明和 source digest/media type | Hint 内容 token |
| `fcv1_` | FileTree build | File ID key fingerprint、排序后的 StaticNode versions | 静态树版本 |
| `hcv1_` | HintCatalog freeze | 排序后的 Hint versions | Hint Catalog 版本 |
| `atv1_` | ArtifactCatalog freeze / lookup | ArtifactTemplate 声明和 generator callback ID | Artifact 逻辑版本、Artifact object key |
| `antv2_` | ArtifactCatalog freeze | Artifact node 声明、callback IDs、关联 `atv1_` | 判断 Artifact node 是否 stale |
| `acv1_` | ArtifactCatalog freeze | 排序后的 Artifact 和 node snapshot entries | 启动 reconciliation、mft1 输入 |
| `mft1_` | RegistryBundle freeze | schema、`fcv1_`、`acv1_` | 共享静态合并拓扑资源版本 |
| `pft4_` | Player 动态文件查询 | `mft1_`、ArtifactInterface.version、声明依赖的状态版本 | 当前玩家动态树版本 |
| `act3_` | ArtifactInterface.tree_nodes | player ID、Artifact ID/version、node ID/version、最终下载名、media type | Artifact 下载 URL 前置条件 |

对象 key 不参与这些 version/token 的 hash。静态 key 是 `static/{module}/{relative_path}`；Artifact key 是 `artifacts/{player_id}/{artifact_version}`。对象存储 VersionId 不参与当前运行时模型。

## 四、Artifact 生成与持久化

### 1. Artifact 的三个数据层

```text
ArtifactTemplate / ArtifactNodeTemplate
  注册期 frozen 声明

ArtifactCatalog
  启动 freeze 后的全局只读模板和 antv2_ effective versions

PlayerArtifact / PlayerArtifactNode / PlayerArtifactState
  玩家范围的数据库状态
```

Artifact 没有独立的全局 HTTP Service。生成入口是可写 `Player.artifacts`，通常由语义化命令中的 module handler 调用。

### 2. 启动 reconciliation 顺序

`ArtifactReconciliationRunner.run()` 的顺序如下：

1. 读取当前 `ArtifactCatalog.snapshot()`。
2. 读取本地旧 snapshot。
3. 检查是否存在 Artifact 但缺少 `PlayerArtifactState` 的迁移期记录。
4. 如果 snapshot 未变且不需要 baseline reconciliation，直接返回。
5. 根据 changed keys 找到受影响的玩家：Artifact 变更、node 变更、node 所属 Artifact 变更都会参与查询。
6. 每个玩家在 `async with session.begin()` 内通过 `PlayerLoader` 加载 writable Player 并执行 reconciliation Service。
7. 事务内加载 Player 的全部 interface，然后执行 `player.artifacts.refresh_stale(player)`。
8. 所有玩家完成后，写入新的 Artifact Catalog snapshot。

启动 reconciliation 使用数据库事务，但显式关闭 checkpoint pre-commit hook；Artifact 对象上传仍然先于 SQL commit，回滚后可能留下由 cleanup service 回收的对象。

### 3. `refresh_stale()` 的顺序

`refresh_stale()` 先处理 Artifact，再处理 node，最后删除已经不在当前 Catalog 或已改指向其他 Artifact 的旧 node：

```text
for each persisted artifact:
  refresh_artifact()

for each currently owned artifact:
  for each current node template:
    refresh_node()

for each persisted node:
  if node template missing or artifact locator changed:
    remove_node()
```

因为 `antv2_` 包含关联的 `atv1_`，Artifact generator revision 变化会同时造成 node version 变化。这样 Artifact 刷新完成后，node generator 即使自身 callback revision 没变，也会因为 effective node version 不匹配而重新执行。

### 4. `generator` 执行和 Artifact 持久化顺序

当 `refresh_artifact()` 或 `generate_artifact()` 判定需要物化 Artifact 时，执行顺序是：

```text
ArtifactTemplate.generator(player)
  -> RawArtifact(data, meta)
  -> ObjectStore.put_bytes(
       data,
       object_key=f"artifacts/{player_id}/{template.version}",
       media_type=template.media_type,
     )
  -> ObjectReference(key, content_digest, media_type, size_bytes)
  -> PlayerArtifact upsert
  -> reload PlayerArtifact + its nodes
```

`PlayerArtifact` upsert 的字段填写顺序和来源是：

| 字段 | 来源 |
| --- | --- |
| `player_id` | 当前 ArtifactInterface 的玩家 ID |
| `artifact_id` | `ArtifactTemplate.artifact_id` |
| `version` | `ArtifactTemplate.version`，即 `atv1_` |
| `object_key` | `ObjectReference.key` |
| `content_digest` | `ObjectReference.content_digest` |
| `media_type` | `ObjectReference.media_type` |
| `size_bytes` | `ObjectReference.size_bytes` |
| `download_name` | `ArtifactTemplate.download_name` |
| `meta` | `RawArtifact.meta` |
| `generated_at` | 当前 UTC 时间 |

写入使用 `(player_id, artifact_id)` 冲突更新，然后重新查询 Artifact 并刷新 `nodes` relationship。重新加载得到的节点会更新 ArtifactInterface 内的 `_artifacts` 和 `_nodes` 映射。

Artifact generator 已存在当前玩家 Artifact 时，`generate_artifact()` 直接返回已有记录，不重复上传；启动 reconciliation 的 `refresh_artifact()` 则会比较数据库 version 与当前 ArtifactTemplate version。

### 5. `node_generator` 执行和 Artifact Node 持久化顺序

当 node 缺失，或 `PlayerArtifactNode.version` 不等于 `ArtifactCatalog.node_version(node_id)` 时，执行 `_materialize_node()`：

#### 5.1 构造 generator 初始输入

先计算：

```text
expected_version = ArtifactCatalog.node_version(template.stable_id)
```

再按模板字段构造可变 `ArtifactNode`：

```text
stable_id       = template.stable_id
path            = template.path
version         = expected_version          # antv2_
display         = template.display
access_rule     = template.access_rule
hidden          = template.hidden
download_name  = template.download_name
artifact_locator = template.artifact_locator
```

#### 5.2 调用 node generator

调用合同为：

```python
runtime_node = await template.node_generator(
    player,
    dict(artifact.meta),
    runtime_node,
)
```

第二个参数是当前 `PlayerArtifact.meta` 的浅复制。generator 可以修改运行时属性，例如 display、hidden 和 download name，但不能改变：

```text
stable_id
artifact_locator
version
path
```

调用返回后依次校验：

1. stable ID 仍等于模板 stable ID。
2. artifact locator 仍等于模板 locator。
3. version 仍等于 effective `antv2_`。
4. path 仍等于 `ArtifactNodeTemplate.path`。
5. path 仍是 canonical virtual path。
6. download name 为空或通过安全下载名校验。

#### 5.3 `PlayerArtifactNode` upsert

校验通过后，按以下顺序填写数据库字段：

| 字段 | 来源 |
| --- | --- |
| `player_id` | 当前 ArtifactInterface 的玩家 ID |
| `node_id` | `ArtifactNodeTemplate.stable_id` |
| `artifact_id` | `ArtifactNodeTemplate.artifact_locator` |
| `path` | `ArtifactNodeTemplate.path`；generator 不得修改 |
| `version` | generator 返回的 effective `runtime_node.version` |
| `display` | generator 返回的 `runtime_node.display.as_dict()` |
| `hidden` | generator 返回的 `runtime_node.hidden` |
| `download_name` | generator 返回的 `runtime_node.download_name` |
| `created_at` | 新记录时的当前 UTC 时间 |
| `updated_at` | 当前 UTC 时间 |

写入使用 `(player_id, node_id)` 冲突更新，然后重新查询并 refresh `PlayerArtifactNode`，再更新 ArtifactInterface 的 `_nodes` 映射。

Artifact node 完成新增或刷新后，调用 `_bump_player_version()` 更新 `PlayerArtifactState.version`，再通过 Player 注入的 mutation callback 清空 Player 的 PlayerFileTree cache。

### 6. 请求内写入顺序

以 Example validation 为例，`POST /api/v1/validations/{validation_id}/attempts` 的调用链是：

```text
Router 找到 ValidationAttempt
  -> Request-ID reserve
  -> session.begin()
  -> PlayerLoader.load(..., writable=True)
     -> load progress
     -> load artifacts
     -> load accounts
     -> load credits
     -> load hints
  -> ValidationAttempt.handler(context, payload)
     -> 业务修改账号/进度
     -> generate_artifact()
        -> artifact generator
        -> object upload
        -> PlayerArtifact upsert
        -> PlayerArtifactState.version + 1
     -> generate_node()
        -> node generator(player, artifact.meta, runtime_node)
        -> PlayerArtifactNode upsert
        -> PlayerArtifactState.version + 1
  -> pre-commit hooks
  -> session commit
  -> 完成 Request-ID cache
```

`generate_artifact()` 和 `generate_node()` 在当前玩家已经拥有对应记录时是幂等返回，不会在每次命令请求中重复执行 generator。模板 stale 刷新由启动 reconciliation 负责。

## 五、请求时动态文件的构建顺序

### 1. Player 和 ArtifactInterface 加载

读请求通过 `get_context()` 创建只读 Player，并按 `PlayerInterfaces` 加载所需 Interface。动态文件端点使用 `PlayerInterfaces.ALL`，因此会加载：

```text
ProgressInterface
ArtifactInterface
AccountInterface
CreditInterface
HintInterface
```

`ArtifactInterface.load()` 的字段来源是：

1. 查询当前玩家全部 `PlayerArtifact`。
2. 通过 `selectinload` 同时加载每个 Artifact 的 `PlayerArtifactNode`。
3. 将 Artifact 放入 `_artifacts[artifact_id]`。
4. 将 node 放入 `_nodes[node_id]`。
5. 查询 `PlayerArtifactState`，不存在时使用 `version = 0`。

此时不会调用 Artifact generator 或 node generator。

### 2. 构建动态 TreeNode 和 `act3_`

第一次调用 `ArtifactInterface.tree_nodes()` 时，按每条 `_nodes` 记录：

1. 找到所属 `_artifacts[node_record.artifact_id]`。
2. 找到当前 Catalog 中的 node template 和 ArtifactTemplate。
3. 从 `PlayerArtifact` 字段构造 `ObjectReference`：key、content digest、media type、size。
4. 计算最终下载名：

```text
node_record.download_name or artifact_template.download_name
```

5. 调用 `FileIdCodec.encode_artifact_content_token()` 生成 `act3_`，输入 player ID、Artifact ID/version、node ID/version、media type 和最终下载名。
6. 使用持久化 path、version、display、hidden 和当前 template access rule 构造 `ArtifactNode`。
7. 创建 `TreeNode`：path、definition、空 children、FileContent 和 `f1_` file ID。

这里的 `act3_` 是延迟生成的请求级内存值，不写入数据库；数据库保存的是构成它的 Artifact、node 和 object metadata。

### 3. Fruiting PlayerFileTree 和 `pft4_`

`MergedFileTree.fruit()`：

1. 保留共享 `MergedFileTree` 拓扑，不复制或修改 root。
2. 按实际 Artifact node path 建立 `nodes_by_path`。
3. 为每个实际 Artifact 文件补全祖先目录 TreeNode；重复祖先只保存一次。
4. 遍历 Slot 时按 path resolve 当前玩家映射；无映射 Slot 在枚举中跳过。
5. 由 `mft1_`、ArtifactInterface.version 和 access_rule 所需状态版本生成 `pft4_`。
6. 将请求级 PlayerFileTree 缓存保存到 Player，而不是 ArtifactInterface。

后续相同 Player 生命周期内的读取复用该 cache；任意影响动态树的 Interface 成功写入都会调用 `Player.invalidate_cache()`。

### 4. Metadata、目录和 URL 请求

动态文件目录、metadata 和 URL 请求都消费当前 PlayerFileTree：

1. 读取目录时按路径链执行 access rule 和 hidden 过滤。
2. metadata 返回稳定 File ID、path、node version、media type、size、`act3_` 和 display；动态 metadata 额外返回 content digest 和最终 download name。
3. 请求 content/download URL 时重新解析当前玩家树。
4. 检查 access rule。
5. 比较 URL path 中的 content-token 和当前 `FileContent.content_token`。
6. 只有 token 匹配才向 ObjectStore 生成预签名 URL。

读取请求不会重新调用 Artifact generator 或 node generator；如果需要根据新的模板版本刷新持久化 Artifact/Node，必须经过启动 reconciliation 或显式写入命令。

## 六、关键不变量

- Registry registration 只描述模块声明；最终静态内容 version 要等对象物化后计算。
- `ArtifactTemplate.version` 描述 Artifact generator/声明；`ArtifactCatalog.node_version()` 额外绑定关联 Artifact version。
- `act3_` 不直接包含 `meta`；meta 通过 Artifact generator 版本变化触发 Artifact refresh，再通过 `antv2_` 触发 node generator。
- Artifact 对象上传发生在 SQL commit 前；事务回滚可能留下对象存储孤儿。
- Service 是全局只读装配对象；玩家状态写入必须参与调用方显式拥有的 transaction。普通 HTTP 写命令使用 Endpoint Executor，内部 Workflow 和 reconciliation 直接组合 `async with session.begin()`、PlayerLoader 与事务内 Service。
- `PlayerArtifactNode.version`、path、display、hidden 和 download name 是数据库中的当前运行结果，不是每次读取时重新运行 generator 得到的临时值。
- 静态 object key、Artifact object key 和 provider VersionId 都不直接构成当前 Content-token。

相关实现：

- [应用装配](../../src/mythos/main.py)
- [RegistryBundle](../../src/mythos/registry/bundle.py)
- [ArtifactCatalog](../../src/mythos/registry/artifacts/catalog.py)
- [ArtifactInterface](../../src/mythos/players/interfaces/artifacts.py)
- [Artifact reconciliation](../../src/mythos/services/artifacts/reconciliation.py)
- [File version/token codec](../../src/mythos/core/file_ids.py)
