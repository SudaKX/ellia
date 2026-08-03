# 运行时组装

## 职责与边界

`create_app()` 是应用装配入口。它不拥有领域 SQL 表、ORM Model 或 Player Interface；唯一直接端点是 `GET /health`。领域数据由模块在 Router 可用前注册，运行期只消费冻结后的 Catalog。

## 启动流程

```text
Settings + RegistryBundle
  -> puzzles.register_all()
  -> StaticAssetPublisher.materialize()
  -> RegistryBundle.freeze(FileIdCodec)
  -> PlayerFactory + checkpoint hook + CommandTransactionExecutor + PlayerLifecycleDispatcher
  -> ArtifactReconciliationRunner + AccountReconciliationRunner
  -> ServiceContainer + ApplicationRuntime
```

`RegistryBundle` 包含 `files`、`progress`、`scripts`、`validations`、`artifacts`、`accounts`、`lifecycle` 七个 Registry；`freeze()` 返回对应的 `RuntimeCatalogs`，并检查静态文件节点与 Artifact 节点的 `stable_id` 不冲突。`ApplicationRuntime` 保存 Catalog、`PlayerFactory`、五个全局 Service、对象存储、命令执行器和生命周期 Dispatcher，挂在 `app.state.runtime`。

## 服务和 HTTP

| 组件 | 全局 Service | Router |
| --- | --- | --- |
| 文件 | `FileService` | `/api/v1/files` |
| 进度 | `ProgressService` | `/api/v1/progress` |
| 脚本 | `ScriptService` | `/api/v1/scripts` |
| 验证 | `ValidationService` | `/api/v1/validations` |
| VirtualAccount | `AccountService` | `/api/v1/vac` |
| 认证 | 请求级 `AuthService` | `/api/v1/auth` |

Artifact 没有生成 Router 或 `ServiceContainer` 成员；它由可写 `Player.artifacts` 在命令内生成。启动期 `ArtifactReconciliationRunner` 是生命周期组件，不是全局请求 Service；它使用本地快照和执行器事务同步变更模板的玩家记录。开发环境额外挂载静态交互页面 `/example/`。

`PlayerLifecycleDispatcher` 同样没有 Router。注册时和既有玩家首次真实登录时，它在认证事务中顺序分发 Construct 回调；Deconstruct 回调预留给未来框架拥有的玩家删除服务。

## 数据对象与 Example

关键对象是 `Settings`、`RegistryBundle`、`RuntimeCatalogs`、`ApplicationRuntime`、`ServiceContainer` 与 `FileIdCodec`。Example 是唯一已注册模块，`register_all()` 调用其 `register()`，覆盖已使用的 Registry。

## 重要约束

- 静态文件必须在 freeze 前完成对象存储物化；Registry/Catalog 在运行期只读。
- Service 是启动期单例，只接收请求级 Player 或 Context，不能保存 Session 或自行提交事务。
- 需要写入的路由必须通过 `CommandTransactionExecutor`；模块只注册内容和 handler，不能添加通用 HTTP 回调。

相关实现：`main.py`、`registry/bundle.py`、`core/runtime.py`、`services/container.py`。
