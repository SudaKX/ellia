# Merged File Tree Versioning

## Purpose

定义启动期合并文件树、Artifact Slot 路径映射、资源与玩家状态版本、动态文件授权及请求级缓存失效行为。

## Requirements

### Requirement: 启动期构建 MergedFileTree

系统 SHALL 在 Registry freeze 完成后构建共享的 `MergedFileTree`，并将静态 FileTree 拓扑与所有 ArtifactNodeTemplate 的 `TreeNodeSlot` 拓扑合并。`MergedFileTree` SHALL 只在启动期构建，运行请求不得修改其拓扑或索引。

#### Scenario: Artifact 模板生成文件 Slot 和前置目录 Slot

- **WHEN** ArtifactNodeTemplate 声明 `/archive/ADMIN_ACCESS.txt` 且静态树没有 `/archive`
- **THEN** MergedFileTree SHALL 包含 `/archive` 的目录 Slot 和 `/archive/ADMIN_ACCESS.txt` 的文件 Slot

#### Scenario: 多个 Artifact 节点共享祖先目录

- **WHEN** 多个 ArtifactNodeTemplate 位于同一个动态目录下
- **THEN** MergedFileTree SHALL 只保存一个对应的目录拓扑节点，并为每个 Artifact 文件保存独立的文件 Slot

#### Scenario: 动态 Slot 与静态拓扑冲突

- **WHEN** Artifact 文件 Slot 与静态文件或静态目录占用同一路径
- **THEN** Registry freeze SHALL 拒绝构建 MergedFileTree

### Requirement: 资源版本链必须覆盖 MergedFileTree

系统 SHALL 使用 `mft1_` 表示 MergedFileTree 的资源版本。该版本 SHALL 由 schema、静态 FileTree 版本和 Artifact Catalog 版本组成，不得重复把 Slot 布局或 access_rule 依赖作为独立 payload 字段写入。

#### Scenario: 静态资源改变时 MergedFileTree 失效

- **WHEN** StaticNode 版本变化并导致 FileTree 版本变化
- **THEN** MergedFileTree.resource_version SHALL 变化

#### Scenario: Artifact Catalog 改变时 MergedFileTree 失效

- **WHEN** ArtifactNodeTemplate、ArtifactTemplate 或其版本链发生变化
- **THEN** MergedFileTree.resource_version SHALL 变化

#### Scenario: 无关玩家状态改变不改变资源版本

- **WHEN** 某个玩家的 progress、accounts 或 credits 状态改变但 Registry Catalog 不变
- **THEN** MergedFileTree.resource_version SHALL 保持不变

### Requirement: Fruiting 使用玩家 path 映射

系统 SHALL 以当前玩家实际拥有的 ArtifactNode path 建立请求级映射，并以 MergedFileTree 中的 Slot path 解析实际节点。Fruiting SHALL 只保存玩家节点和其祖先目录映射，不得复制或修改 MergedFileTree。

#### Scenario: 已拥有 Artifact 节点被 resolve

- **WHEN** PlayerArtifactNode 对应一个 MergedFileTree 文件 Slot
- **THEN** 访问该 Slot 时 SHALL 使用当前玩家实际 Artifact TreeNode

#### Scenario: Fruiting 补全祖先目录

- **WHEN** 玩家拥有 `/archive/ADMIN_ACCESS.txt`
- **THEN** 请求级映射 SHALL 同时包含 `/archive/ADMIN_ACCESS.txt` 文件节点和 `/archive` 目录节点

#### Scenario: 多个节点共享祖先映射

- **WHEN** 玩家拥有 `/archive/ADMIN_ACCESS.txt` 和 `/archive/ADMIN_LOG.txt`
- **THEN** 请求级映射 SHALL 只创建一个 `/archive` 目录节点

#### Scenario: Slot 没有玩家映射

- **WHEN** 访问一个没有对应玩家 ArtifactNode 的 Slot
- **THEN** 目录枚举和递归树 SHALL 跳过该 Slot，文件查找 SHALL 返回未找到

### Requirement: Artifact 节点 path 必须稳定

系统 SHALL 要求 node_generator 返回的 ArtifactNode path 等于其 ArtifactNodeTemplate path。node_generator 不得修改 path；stable_id、artifact_locator、version 和 path SHALL 作为不可变节点身份字段。

#### Scenario: Generator 返回不同 path

- **WHEN** node_generator 返回与模板不同的 path
- **THEN** Artifact 节点写入 SHALL 失败，并且该节点不得进入可用动态文件树

#### Scenario: Generator 保持模板 path

- **WHEN** node_generator 返回与模板相同的 path
- **THEN** 节点 SHALL 可以继续持久化、fruiting 和被动态文件查询使用

### Requirement: PlayerInterface 提供统一状态版本

所有可作为文件 access_rule 依赖的 PlayerInterface SHALL 符合 `VersionedPlayerInterface` Protocol，并提供当前玩家范围的 `version`。Player SHALL 能够依据 `PlayerInterfaces` bitmask 返回稳定顺序的状态版本向量。

#### Scenario: 进度或账号状态更新

- **WHEN** ProgressInterface 或 AccountInterface 通过合法写入路径改变数据库状态
- **THEN** 对应 Interface.version SHALL 在同一事务状态中变化

#### Scenario: Artifact 状态更新

- **WHEN** 玩家 Artifact 或 ArtifactNode 被新增、刷新或移除
- **THEN** ArtifactInterface.version SHALL 变化

#### Scenario: 未提供状态版本的 Interface 被声明为依赖

- **WHEN** access_rule 声明依赖一个没有有效 version 的 PlayerInterface
- **THEN** Registry 或版本计划构建 SHALL 拒绝该依赖

### Requirement: access_rule 依赖必须进入 callback ID

文件 StaticNode 和 ArtifactNode 的 access_rule SHALL 通过现有 module handler 显式声明 `PlayerInterfaces` 依赖。依赖 mask SHALL 纳入 callback ID 的规范化生成输入，并通过现有 StaticNode、ArtifactNode 和 Catalog 版本链传播。

#### Scenario: 账号依赖发生变化

- **WHEN** 同一个 access_rule 的依赖从 NONE 变为 ACCOUNTS，或依赖 mask 发生其他变化
- **THEN** callback ID SHALL 变化，并最终导致相关 FileCatalog 或 ArtifactCatalog 版本变化

#### Scenario: 未声明依赖的文件 access_rule

- **WHEN** 文件节点注册了 access_rule 但 callback 没有依赖声明
- **THEN** 注册或 freeze SHALL 失败

#### Scenario: 无状态 access_rule

- **WHEN** access_rule 不读取任何玩家 Interface 且显式声明 PlayerInterfaces.NONE
- **THEN** 注册 SHALL 成功，且该规则不要求动态状态版本

### Requirement: 动态树版本必须覆盖依赖状态

系统 SHALL 使用 `pft4_` 生成当前玩家动态文件树版本。`pft4_` SHALL 由 MergedFileTree.resource_version、ArtifactInterface.version 和 MergedFileTree access_rule 依赖所需的 PlayerInterface 版本组成。

#### Scenario: 账号切换改变动态 ETag

- **WHEN** 玩家账号状态改变并导致账号 access_rule 结果可能改变
- **THEN** `/files/d/version` SHALL 返回新的 pft4_，携带旧 ETag 请求不得返回 `304`

#### Scenario: 进度变化改变动态 ETag

- **WHEN** 玩家 progress.version 改变并导致进度 access_rule 结果可能改变
- **THEN** `/files/d/version` SHALL 返回新的 pft4_

#### Scenario: 未变化时复用 ETag

- **WHEN** MergedFileTree.resource_version 和所有计划内状态版本均未改变，且请求的 If-None-Match 等于当前 ETag
- **THEN** `/files/d/version` SHALL 返回 `304`

#### Scenario: 无关 credits 状态不改变文件版本

- **WHEN** 当前文件 access_rule 未声明 CREDITS，且只有 credits.version 改变
- **THEN** pft4_ SHALL 保持不变

### Requirement: 请求级缓存必须显式失效

Player SHALL 提供 `invalidate_cache()`，并在任何可能影响当前动态文件树的 PlayerInterface 写入成功后清空请求级 PlayerFileTree 缓存。请求缓存 SHALL 不依赖资源或状态版本向量作为 key。

#### Scenario: 同一请求内进度更新后重新查询文件树

- **WHEN** PlayerFileTree 已构建，随后 ProgressInterface 在同一请求内成功更新状态
- **THEN** Player.invalidate_cache() SHALL 清空旧树，下一次动态文件查询 SHALL fruiting 新的 PlayerFileTree

#### Scenario: 同一请求内账号切换后重新查询文件树

- **WHEN** PlayerFileTree 已构建，随后 AccountInterface 成功登录或登出
- **THEN** 下一次动态文件查询 SHALL 不得复用账号切换前的 PlayerFileTree

#### Scenario: 请求失败后的缓存处理

- **WHEN** 状态写入事务回滚或请求异常结束
- **THEN** 当前请求缓存 SHALL 不得泄漏到后续请求

### Requirement: 动态文件查询必须在 PlayerFileTree 上执行授权过滤

动态目录、递归树、metadata 和内容 URL 授权 SHALL 通过 PlayerFileTree resolve Slot 后，再执行现有 hidden、路径链 access_rule 和 content-token 校验。tree version 不得替代每次请求的 access_rule 授权检查。

#### Scenario: 已拥有但无权访问的 Artifact 文件

- **WHEN** 玩家拥有 ArtifactNode 但其 access_rule 返回 false
- **THEN** 文件不得出现在目录或树响应中，直接访问文件 metadata 或 URL SHALL 保持现有拒绝语义

#### Scenario: 已拥有且可访问的 Artifact 文件

- **WHEN** Slot 能 resolve 到玩家节点且路径链 access_rule 均允许
- **THEN** 文件 SHALL 出现在动态目录或树响应中，并返回当前 content-token

#### Scenario: metadata 和动态版本一致

- **WHEN** 请求动态文件 metadata
- **THEN** metadata.tree_version SHALL 等于当前 `/files/d/version` 的 pft4_ 值

### Requirement: Credits interface version SHALL cover all credit balances

作为文件 access_rule 可能依赖的接口，`credits.version` SHALL 表示玩家级聚合状态版本：任何 credit 余额的成功写入（发放、扣费、行创建、reconciliation 删除）SHALL 递增该版本。任何可能改变依赖 CREDITS 的 access_rule 结果的余额变化都 SHALL 使 `pft4_` 动态树版本变化。

#### Scenario: Custom credit change invalidates dynamic tree version

- **WHEN** 某文件 access_rule 声明 CREDITS 依赖，且任意已注册 credit（含自定义 credit）的余额通过合法写入路径变化
- **THEN** `/files/d/version` SHALL 返回新的 `pft4_`

#### Scenario: Aggregate version never regresses

- **WHEN** reconciliation 删除孤儿余额行或任一 credit 余额写入成功
- **THEN** `credits.version` SHALL 不小于写入前的值，树版本不得回退到旧值
