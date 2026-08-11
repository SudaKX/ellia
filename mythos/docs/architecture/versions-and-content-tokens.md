# Version 与 Content-Token

本文说明 Mythos 当前实现中各类 `Version`、对象内容摘要、公开文件 ID 和 `content_token` 的职责边界。所有指纹都由规范化 JSON 计算 SHA-256，并带有显式 schema 前缀；不同前缀代表不同的失效范围，不能互换。

## 设计边界

Mythos 使用四种不同的标识：

1. `stable_id` 是模块声明的逻辑身份。它在内容改变时保持不变，用于注册表、数据库关联和生成器定位。
2. `Version` 是声明或 Catalog 的内容版本。它回答“这个定义是否改变了”，不是对象存储的历史版本号。
3. `File ID` 是给客户端使用的稳定公开定位符。`f1_` 文件 ID 和 `h1_` Hint ID 使用服务端 HMAC，不携带内容版本，也不是授权凭据。
4. `content_token` 是某个可下载内容的当前快照令牌。签发预签名 URL 前必须匹配当前令牌；旧令牌返回 `412`。

对象存储的 bucket versioning 已停用。`VersionId` 不参与当前模型、版本计算或 URL 授权；当前运行时也不读取、持久化或传递它。静态和 Artifact 对象都使用确定性的逻辑 key，内容变化时覆盖同一个 key。

## 标识总览

| 对象 | 所属字段或属性 | 前缀 | 主要输入 | 用途 |
| --- | --- | --- | --- | --- |
| `ArtifactTemplate` | `ArtifactTemplate.version` | `atv1_` | ID、媒体类型、默认下载名、generator callback ID | 判断玩家 Artifact 是否需要刷新 |
| `ArtifactNodeTemplate` | `ArtifactCatalog.node_version()` | `antv2_` | stable ID、Artifact locator、ArtifactTemplate version、路径、显示属性、隐藏状态、下载名、node generator 和 access-rule callback ID | 判断玩家 Artifact node 是否需要刷新 |
| `StaticNode` | 冻结时写入 `StaticNode.version` | `snv1_` | 节点元数据、源 locator、源 SHA-256、源媒体类型、下载名、access-rule callback ID | 静态节点版本和静态文件内容令牌 |
| `Hint` | `hint_version()` 的结果 | `hv1_` | Hint 元数据、源 SHA-256、源媒体类型、下载名、显示属性、VTB 成本、access-rule callback ID | Hint 内容令牌和 Hint 内容变更判断 |
| Artifact Catalog | `ArtifactCatalog.version` | `acv1_` | 所有 Artifact 和 ArtifactNode 的 snapshot entries | 启动期 reconciliation 和玩家树版本 |
| Hint Catalog | `HintCatalog.version` | `hcv1_` | 按 stable ID 排序的 `(stable_id, hv1_)` | Hint Catalog 快照版本 |
| `VirtualAccountTemplate` | `VirtualAccountTemplate.version` | `vat1_` | account ID、显示名、权限和 JSON metadata | 虚拟账号模板变更判断 |
| VirtualAccount Catalog | `VirtualAccountCatalog.template_version` | `vac1_` | 所有 VirtualAccount snapshot entries | 启动期账号模板 reconciliation |
| 静态 `FileCatalog` | `FileCatalog.version` | `fcv1_` | schema、File ID signing-key fingerprint、所有 `(stable_id, StaticNode.version)` | 静态内容 Catalog 版本 |
| 静态 `FileTree` | `FileTree.tree_version` | `fcv1_` | schema、File ID signing-key fingerprint、所有 `(stable_id, StaticNode.version)` | 静态树列表、树接口和 ETag |
| `MergedFileTree` | `MergedFileTree.resource_version` | `mft1_` | schema、静态 FileTree version、Artifact Catalog version | 启动期共享静态合并拓扑和 Slot 资源版本 |
| 玩家 `PlayerFileTree` | `PlayerFileTree.tree_version` | `pft4_` | `mft1_`、ArtifactInterface.version、声明依赖的 PlayerInterface 状态版本 | 动态树列表、树接口和 ETag |
| Artifact 文件内容 | `FileContent.content_token` | `act3_` | player ID、artifact ID、ArtifactVersion、node ID、node version、媒体类型、最终下载名 | Artifact content/download URL 的当前快照校验 |

通用 `TemplateSnapshot` 默认使用 `tv1_` 计算指纹，但 Artifact Catalog 明确传入 `acv1_`。这里的前缀属于协议的一部分，新增 schema 时应递增前缀版本，而不是复用旧前缀解释新 payload。

## 数据对象与字段

### `ObjectReference`

`ObjectReference` 只描述已经物化的对象：

- `key`：对象存储中的相对 key。
- `content_digest`：`sha256:<64 位小写十六进制摘要>`。
- `media_type`：响应媒体类型。
- `size_bytes`：对象大小。

它没有 `VersionId` 字段。摘要是对象字节内容的事实来源；对象 key 主要用于定位，不承担版本语义。对象存储应保持未启用或已暂停版本管理，不能把 provider 的版本号当作 Mythos 的内容版本。

### `FileContent`

`FileContent` 将 `ObjectReference` 与客户端可见的下载信息绑定：

- `object_ref`：实际对象。
- `download_name`：最终有效的下载名。
- `content_token`：签发 URL 时必须提供的当前令牌。

静态 FileTree 中，`content_token == StaticNode.version`。Hint Catalog 中，`content_token == Hint.version`。Artifact node 中，`content_token` 使用 `act3_`，因为它还必须绑定玩家和运行时最终下载名。

### `VirtualNode` 与 `StaticNode`

`VirtualNode.version` 是树节点的版本字段，目录也有版本，但只有文件节点会生成 `FileContent`。Static registry 在 freeze 时根据已物化对象调用 `static_node_version()`，用计算结果替换注册期的 runtime version；因此手工声明的旧版本值不是静态内容版本的最终来源。

`StaticNodeSpec` 是注册期声明对象，转换为 runtime `StaticNode` 后再由 freeze 计算版本。JSON manifest 不包含手工 `version` 字段。

### `ArtifactTemplate`、`ArtifactNodeTemplate` 与运行时记录

`ArtifactTemplate.version` 只描述 Artifact 定义，不描述某个玩家生成的字节。它包含 generator 的稳定 callback ID，因此生成逻辑升级时必须通过 `module_handler(module)(revision)` 更新 callback revision。

`ArtifactCatalog.node_version()` 描述节点定义、对应 ArtifactTemplate version 和 node generator/access-rule callback。node generator 可以读取 `RawArtifact.meta` 并生成运行时节点；写入数据库前会校验 stable ID、Artifact locator 和 effective node version，任何修改都会被拒绝。

数据库中保存对应快照：

- `PlayerArtifact.version` 保存已应用的 `ArtifactTemplate.version`。
- `PlayerArtifactNode.version` 保存已应用的 `ArtifactCatalog.node_version()`。
- `PlayerArtifactState.version` 是玩家 Artifact 树的单调递增状态版本，不是 Artifact 内容 hash。

Artifact 的 `RawArtifact.meta` 用于 node generator 输入，不直接构成模板版本。生成的字节通过 `ObjectReference.content_digest` 记录；相同玩家和 ArtifactVersion 的 generator 必须保持确定性。

## 版本生成规则

### StaticNode：`snv1_`

`static_node_version()` 的规范化输入为：

```text
schema
stable_id
kind: file | directory
path
display
hidden
source_locator
source_file_hash
source_media_type
download_name
access_rule_callback_id
```

文件源在启动期由 `StaticAssetPublisher` 全量读取并计算 SHA-256。只有登记表中的摘要和媒体类型都没有变化时才复用已登记对象；否则上传到固定 key 后更新登记。mtime 不是版本输入。

### Hint：`hv1_`

`hint_version()` 的输入为：

```text
schema
stable_id
source_locator
source_file_hash
source_media_type
download_name
display
vtb_cost
access_rule_callback_id
```

Hint Catalog 同时构造 `FileContent`，直接把该 Hint version 作为 content token。购买或 disclosure 状态只影响玩家是否能看到和读取 Hint，不改变 Hint 本身的内容 token。

### ArtifactTemplate：`atv1_`

输入为 `artifact_id`、`media_type`、默认 `download_name` 和 generator callback ID。Artifact Catalog 的 snapshot entry 同时保存定义和该版本，按 `(kind, template_id)` 排序后计算 `acv1_`。

### ArtifactNodeTemplate：`antv2_`

输入为 stable ID、Artifact locator、对应 ArtifactTemplate.version、path、display、hidden、声明的 download name、node generator callback ID 和 access-rule callback ID。运行时 node 的下载名可以覆盖模板或 Artifact 默认值，但最终名称必须进入 Artifact content token。

### FileCatalog 与 FileTree：`fcv1_`

静态 Catalog 构建后使用以下输入计算 `FileCatalog.version`；`FileTree.tree_version` 直接使用该值：

```text
schema
file_id_key_fingerprint
按 stable_id 排序的 (stable_id, StaticNode.version)
```

由于 `StaticNode.version` 已包含路径、显示属性和源内容摘要，静态文件内容、文件名、访问回调和目录元数据的变更都会传播到 `fcv1_`。File ID signing key 变化也会使树版本变化，因为公开 ID 映射随之变化。

### MergedFileTree：`mft1_`

`MergedFileTree` 在 Registry freeze 后只构建一次，物理合并静态 `FileTree` 和所有 ArtifactNodeTemplate 的 `TreeNodeSlot`。其资源版本不重复写入 Slot 布局，而是由以下 payload 计算：

```text
schema: 1
static_tree_version: fcv1_
artifact_catalog_version: acv1_
```

`TreeNodeSlot` 以 path 作为请求期映射键；目录 Slot 的 `artifact_locator` 为 `None`，文件 Slot 带有 Artifact locator 和 File ID。静态文件、静态目录和 Slot 的同路径冲突在 freeze 时拒绝。

### PlayerFileTree：`pft4_`

`PlayerFileTree` 不复制 `MergedFileTree`。请求期只通过 `MergedFileTree.fruit()` 保存当前玩家实际 Artifact 文件节点和祖先目录的 `nodes_by_path` 映射。`FileIdCodec.encode_player_tree_version()` 使用以下 payload：

```text
schema: 4
merged_file_tree_version: mft1_...
state_versions:
  artifacts: ArtifactInterface.version
  accounts: AccountInterface.version       # 仅在 access_rule 声明时出现
  progress: ProgressInterface.version     # 仅在 access_rule 声明时出现
```

静态文件 access_rule 通过 `module_handler(..., dependencies=PlayerInterfaces.X)` 显式声明依赖，但当前静态文件路由只支持 `PROGRESS | ACCOUNTS`。Artifact Node access_rule 的动态文件路由加载全部 Interface，并将受支持的已声明状态版本纳入 `pft4_`；Hint Interface 没有状态版本，不能作为动态文件 access_rule 的版本依赖。依赖 mask 进入 callback ID，继续沿 StaticNode/ArtifactNode 和 Catalog 版本链传播。`Player.invalidate_cache()` 负责请求内缓存失效，版本向量不作为缓存 key。

## Content-Token 生成与校验

### StaticFile 和 Hint

静态文件和 Hint 使用节点或 Hint 的内容版本作为 token：

```text
StaticFile: content_token = StaticNode.version
Hint:       content_token = Hint.version
```

这类 token 绑定注册定义和源摘要，但不绑定玩家。授权仍由当前玩家和节点 access rule 执行。

### ArtifactFile：`act3_`

Artifact node 的 payload 为：

```text
schema: 3
player_id
artifact_id
artifact_version: PlayerArtifact.version
node_id: ArtifactNode stable ID
node_version: PlayerArtifactNode.version
download_name: 最终有效下载名
media_type
```

`ArtifactNodeTemplate.download_name` 会作为运行时 node 的初始下载名并持久化到 `PlayerArtifactNode`；如果运行时 node 没有下载名，则回退到 `ArtifactTemplate.download_name`。因此最终有效下载名由 `PlayerArtifactNode.download_name` 或 ArtifactTemplate 默认值提供。`act3_` 使用 SHA-256，不使用 File ID signing key；player ID 在 payload 中，所以不同玩家的 Artifact token 不可互用。

FileService 的 URL 流程是：

1. 用当前玩家树解析 File ID。
2. 检查文件路径链上的 access rule。
3. 比较 URL 中的 token 与当前 `FileContent.content_token`。
4. 仅在全部检查通过后，使用当前 `ObjectReference` 生成预签名 URL。

因此 token 不是独立授权凭据，也不能绕过 access rule。token 不匹配抛出 `FileContentVersionMismatchError`，由 API 映射为 `412 Precondition Failed`。

### File ID 与 Token 的关系

`f1_` 和 `h1_` 使用 HMAC：

```text
f1_: HMAC(file:v1, stable_id)
h1_: HMAC(hint:v1, stable_id)
```

它们用于公开路由定位，避免直接暴露内部 stable ID。File ID 不能代替 content token；同一个 File ID 可能在内容版本更新后继续指向同一逻辑文件，但旧 token 必须失效。

## 失效传播

| 变化 | 直接变化 | 传播结果 |
| --- | --- | --- |
| 静态源字节改变 | `ObjectReference.content_digest`、`snv1_` | `fcv1_` 改变；旧静态 token 返回 `412` |
| 静态媒体类型、下载名、显示属性或 access callback revision 改变 | `snv1_` | `fcv1_` 改变；文件 metadata 和 token 更新 |
| Hint 源、显示属性、VTB 成本或 access callback revision 改变 | `hv1_`、`hcv1_` | Hint token 更新；已有 disclosure 不会改变新内容的版本规则 |
| ArtifactTemplate 定义或 generator callback revision 改变 | `atv1_`、`acv1_` | reconciliation 刷新已有玩家 Artifact |
| ArtifactTemplate 定义或 generator callback revision 改变 | `atv1_`、对应 `antv2_`、`acv1_` | reconciliation 刷新 Artifact，并重新执行其 node generator |
| ArtifactNodeTemplate 定义或 callback revision 改变 | `antv2_`、`acv1_` | reconciliation 刷新受影响玩家 node |
| 玩家 Artifact/Artifact node 创建、刷新或删除 | `PlayerArtifactState.version`、`ArtifactInterface.version` | `pft4_` 改变，Player 树缓存清空 |
| 文件 access_rule 依赖的账号或进度改变 | 对应 `PlayerInterface.version` | 相关玩家的 `pft4_` 改变；旧 ETag 不返回 `304` |
| Artifact 的版本、node 版本、媒体类型或最终下载名改变 | `act3_` | 旧 Artifact token 返回 `412` |
| File ID signing key 改变 | `f1_`/`h1_` 映射和 key fingerprint | 新 File ID 与新的 `fcv1_` 生效 |

启动期先物化静态源，再 freeze registry 和 Catalog；registry freeze 后不能再注册通用内容。Artifact Catalog 变化由启动期 reconciliation 应用到数据库，应用在同步成功前不会进入 ready 状态。

## 对象存储约束

当前对象 key 为：

```text
static/{module}/{relative_path}
artifacts/{player_id}/{artifact_version}
```

key 不包含 digest、mtime 或 S3 VersionId。静态源摘要变化时写回同一个静态 key；Artifact 版本变化时使用新的 ArtifactVersion key。未启用对象存储版本管理时，旧静态字节会被覆盖，不存在可供 Mythos 选择的 provider 历史版本；已签发的旧静态预签名 URL 在自身 TTL 内可能读取覆盖后的新字节，这是当前固定 key、无 VersionId 策略的接受行为。SQL 事务回滚可能留下已上传但未被数据库引用的 Artifact 对象，由 `ArtifactCleanupService` 最佳努力清理。

bucket 仍应保持私有，应用只向客户端返回短期预签名 URL。对象存储只需要支持应用使用的写入和读取预签名能力；不要启用 bucket versioning，也不要把 provider 的版本控制语义暴露给 Mythos。

## 非内容版本

并非所有名为 `version` 的字段都是内容版本或 content-token：

- `PlayerProgress.version` 是玩家进度和 checkpoint 状态的整数版本。
- `PlayerCredits.version` 是 VTB 余额状态的整数版本。
- `PlayerVirtualAccountState.version` 是当前虚拟账号状态的整数版本。
- `PlayerArtifactState.version` 是 Artifact 动态树的整数版本，并由 `ArtifactInterface.version` 暴露，作为 `pft4_` 的输入。

这些玩家状态版本用于状态同步、条件更新或树失效，不由对象字节直接 hash，也不依赖 RustFS/S3 的版本管理。`vat1_`、`vac1_` 虽然是 SHA-256 Catalog 版本，但它们只描述虚拟账号定义，不生成文件 content-token。

## 相关实现

- `src/mythos/registry/catalog_snapshots.py`：规范化 JSON 指纹和 Catalog snapshot。
- `src/mythos/registry/artifacts/versions.py`：ArtifactTemplate 与 ArtifactNodeTemplate 版本。
- `src/mythos/registry/files/versions.py`：StaticNode 版本。
- `src/mythos/registry/files/catalog.py`：`FileCatalog` 和 `fcv1_`。
- `src/mythos/registry/files/registry.py`：静态源物化、freeze 和 FileContent 构造。
- `src/mythos/registry/files/tree.py`：`FileTree` 和 `fcv1_`。
- `src/mythos/registry/files/merged_tree.py`：`MergedFileTree`、`TreeNodeSlot` 拓扑和 `mft1_`。
- `src/mythos/registry/files/player_tree.py`：`PlayerFileTree`、Slot resolve 和 `pft4_` 消费。
- `src/mythos/registry/hints/definitions.py`、`src/mythos/registry/hints/catalog.py`：Hint 版本和 `hcv1_`。
- `src/mythos/registry/accounts/versions.py`、`src/mythos/registry/accounts/catalog.py`：`vat1_` 和 `vac1_`。
- `src/mythos/core/file_ids.py`：`f1_`、`h1_`、`act3_` 和 `pft4_` 编码。
- `src/mythos/services/files/service.py`：授权、token 校验和预签名 URL。
- `src/mythos/services/files/static_assets.py`：静态源摘要物化和固定对象 key。
- `src/mythos/players/interfaces/artifacts.py`：Artifact 生成、持久化、实际节点和动态 token。
