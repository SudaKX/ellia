# Artifact 系统

本文档说明 Mythos 后端中 **玩家专属动态文件（Artifact）** 的设计、实现与使用方式。

---

## 1. 概述

**Artifact** 是指根据玩家状态动态生成、并挂到该玩家虚拟文件树中的文件。典型场景包括：

- 根据玩家答案生成专属报告
- 解锁隐藏文档或日志
- 动态生成与玩家进度相关的资源文件

Artifact 与静态文件共享同一个 `stable_id` 命名空间和文件树，但内容由生成器在运行时决定，并按玩家隔离存储。

---

## 2. 核心概念

| 类型 | 说明 |
|---|---|
| `ArtifactTemplate` | Artifact 内容模板，包含内容生成器、媒体类型、下载名、版本号 |
| `ArtifactNodeTemplate` | Artifact 在文件树中的节点模板，包含 `stable_id`、默认路径、显示参数、访问规则 |
| `RawArtifact` | 内容生成器返回的原始数据对象（`data: bytes` + `meta: dict`） |
| `ArtifactNode` | 运行时节点，内容生成后可被节点生成器修改 `path` / `display` / `hidden` / `revision`，但 `stable_id` 与 `artifact_locator` 不可变更 |
| `ArtifactRegistry` / `ArtifactCatalog` | 启动时注册并冻结的 Artifact 注册表 |

---

## 3. 注册与冻结

模块在启动时通过 `RegistryBundle` 注册 Artifact：

```python
from mythos.registry.artifacts import ArtifactTemplate, ArtifactNodeTemplate, RawArtifact

async def _generator(context: CommandContext) -> RawArtifact:
    return RawArtifact(b"hello", meta={"ok": True})

async def _node_generator(context, node: ArtifactNode) -> ArtifactNode:
    node.path = "/dynamic/report.txt"
    return node

registries.artifacts.register_template(
    ArtifactTemplate(
        artifact_id="intro.report",
        revision="1",
        media_type="text/plain",
        download_name="report.txt",
        generator=_generator,
    )
)
registries.artifacts.register_node(
    ArtifactNodeTemplate(
        stable_id="intro.report-node",
        path="/dynamic/report.txt",
        revision="1",
        artifact_locator="intro.report",
        display=DisplayParams(label="Report", icon="document"),
        node_generator=_node_generator,
    )
)
```

`RegistryBundle.freeze()` 会跨静态文件注册表和 Artifact 注册表检查 `stable_id` 唯一性，确保启动期即发现冲突。

---

## 4. 持久化模型

涉及两张表，迁移文件为 `mythos/migrations/versions/0005_player_artifacts.py`：

- `player_artifacts`：每个玩家每个 `artifact_id` 一行，记录当前版本的对象 key、版本 ID、内容摘要、媒体类型等
- `player_artifact_nodes`：每个 Artifact 节点一行，记录节点在文件树中的路径、显示参数、是否隐藏等

每个玩家对同一个 `artifact_id` 只有一个实例；重新生成时会**upsert**旧记录，不会新增。

---

## 5. 生成流程

生成通常由 command 触发：

```python
nodes = await player.artifacts.generate("intro.report", context)
```

内部流程：

1. 从 `ArtifactCatalog` 获取 `ArtifactTemplate` 与关联的 `ArtifactNodeTemplate`
2. 调用 `template.generator(context)` 得到 `RawArtifact`
3. 计算 SHA-256 digest，构造对象 key：`artifacts/{player_id}/{artifact_id}/{revision}/{digest}`
4. 调用 `ObjectStore.put_bytes(...)` 上传对象
5. 使用 `INSERT ... ON CONFLICT DO UPDATE` 原子更新 `PlayerArtifact`
6. 对每个节点模板：
   - 创建运行时 `ArtifactNode`
   - 调用 `node_generator(context, node)`
   - 原子 upsert `PlayerArtifactNode`
7. 清空 `ArtifactInterface` 内的 `PlayerFileTree` 请求级缓存

---

## 6. 动态文件树

`PlayerFileTree` 在请求内把静态文件树与玩家 Artifact 节点合并：

```python
player_tree = player.artifacts.get_tree(static_tree, file_ids)
```

- 深拷贝静态树并插入 Artifact 节点
- `tree_version` = 静态版本 + Artifact 内容 hash
- 同一请求内多次访问会复用缓存；重新生成后缓存失效

文件服务通过该合并树提供动态端点。

---

## 7. 端点

### 静态端点（仅需要 progress interface）

- `GET /files/ls`
- `GET /files/s/ls`
- `GET /files/tree`
- `GET /files/s/tree`
- `GET /files/version`

### 动态端点（需要 progress + artifacts interface）

- `GET /files/d/ls`
- `GET /files/d/tree`
- `GET /files/d/version`
- `GET /files/{file_id}`
- `GET /files/{file_id}/{content_token}/content-url`
- `GET /files/{file_id}/{content_token}/download-url`

动态端点会返回合并后的静态 + Artifact 文件树；静态端点不受 Artifact 影响。

---

## 8. 安全

Artifact 文件使用独立的 content token（前缀 `act1_`），payload 包含 `player_id`：

```
artifact-content:v1:{player_id}:{stable_id}:{revision}:{object_key}:{version_id}:{media_type}:{download_name}
```

这样 content URL 被绑定到具体玩家，玩家 A 的 URL 无法在玩家 B 的会话中通过校验。

---

## 9. 性能优化

### 9.1 Player interface 懒加载

`Player` 不再在构造时加载所有 interface：

- `PlayerFactory.create(...)` 只返回轻量 `Player`
- 使用方按需调用 `await player.load_progress()` / `await player.load_artifacts()`
- 访问未加载的 interface 会抛出 `PlayerInterfaceNotLoadedError`

这样 `/progress`、`/scripts` 等不需要 Artifact 的端点就不会查询 artifact 表。

### 9.2 Bitmap 依赖

`get_context(interfaces: PlayerInterfaces)` 让路由声明自己需要哪些 interface：

```python
context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.PROGRESS))]
context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ARTIFACTS))]
```

### 9.3 Artifact 请求级缓存

`ArtifactInterface` 在同一请求内缓存构建好的 `PlayerFileTree`，避免重复深拷贝静态树。

---

## 10. 并发与一致性

`PlayerArtifact` 与 `PlayerArtifactNode` 的更新使用 SQLite `INSERT ... ON CONFLICT DO UPDATE`，基于 `(player_id, artifact_id)` 与 `(player_id, node_id)` 主键保证：

- 并发生成同一 Artifact 时不会插入重复行
- 重新生成时旧记录被原子覆盖

---

## 11. 孤儿对象清理

Artifact 对象在上传之后才提交 SQL 事务，因此事务回滚可能留下 RustFS 孤儿对象。提供 `ArtifactCleanupService`：

```python
service = ArtifactCleanupService(object_store)
result = await service.sweep(session)  # {"listed": ..., "referenced": ..., "deleted": ..., "skipped": ...}
```

它会列出 `artifacts/` 前缀下的对象，并删除未被 `PlayerArtifact` 引用的 key。建议通过外部定时任务（如 Celery / CronJob）周期性调用。

---

## 12. 测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_artifact_interface.py` | `ArtifactInterface` 生成、加载、缓存、upsert、token、隐藏节点 |
| `tests/test_artifact_registry.py` | Artifact 注册、冻结、stable_id 冲突检查 |
| `tests/test_dynamic_files.py` | 动态文件端点集成测试 |
| `tests/test_artifact_cleanup.py` | `ArtifactCleanupService` 清理逻辑 |
| `tests/test_player.py` | Player interface 懒加载与异常路径 |
| `tests/_helpers/object_store.py` | 共享的 `FakeObjectStore` 测试替身 |

---

## 13. 相关文件

- `mythos/src/mythos/players/player.py`
- `mythos/src/mythos/players/factory.py`
- `mythos/src/mythos/players/dependencies.py`
- `mythos/src/mythos/players/interfaces/artifacts.py`
- `mythos/src/mythos/registry/artifacts/`（definitions/registry/catalog）
- `mythos/src/mythos/registry/files/player_tree.py`
- `mythos/src/mythos/services/files/service.py`
- `mythos/src/mythos/services/files/router.py`
- `mythos/src/mythos/services/artifacts/cleanup.py`
- `mythos/src/mythos/core/file_ids.py`
- `mythos/migrations/versions/0005_player_artifacts.py`
