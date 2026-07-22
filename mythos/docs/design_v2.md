# Mythos 后端设计 V2

本文取代 V1 中与玩家访问、Effect、Service 和注册器有关的约定。认证、异步 SQLite、JWT、Refresh Cookie 和 Request-ID 短时去重保持不变。

## 1. 分层

- `persistence/` 保存 SQLAlchemy 记录模型。`PlayerRecord` 是数据库记录，不向业务模块暴露。
- `players/` 提供请求级 `Player` 聚合对象及其数据库访问 Interface。
- `services/` 保存应用级全局 Service。Service 仅读取 Player 和冻结后的注册内容，不保存请求、Session 或玩家状态。
- `registry/` 按动态内容类型维护注册和冻结逻辑。
- `endpoints/` 负责 HTTP、Action、事务、RequestCache 和模块回调派发。

## 2. Player 与 Interface

`PlayerFactory` 在每个请求中以 `AsyncSession` 和 JWT 身份创建一个 `Player`。`Player` 组合多个 Interface；V2 初始仅实现 `ProgressInterface`。

```text
Player
└── progress: ProgressInterface
```

Interface 的读取方法返回当前数据库快照。写入方法不直接写数据库，而是返回框架创建的 `PendingEffect`。只读 Player 不能构造写入 Effect，供视图回调和 Service 路由使用。

## 3. Effect 与事务

模块回调先通过 Player 读取前置条件，再按业务顺序组织 `PendingEffectPlan` 并返回 `EffectAction`。Plan 仅收集和冻结 Effect，不使用 preview 或内存状态投影。

每个 Effect 绑定其 Interface 的私有执行回调。EffectAction 在唯一回调的外层数据库事务内依次调用回调。任一回调失败时，事务回滚；成功提交后才构造和缓存 HTTP 响应。

V2 暂不提供统一的乐观锁或并发版本保护。具体 Interface 在出现真实并发约束时，于其 Effect 执行回调中定义条件更新、唯一约束或其他保护机制。

## 4. Service

每个 Service 是启动期创建一次的全局对象，并拥有自己的 FastAPI Router：

```text
services/files/    # FileService 与文件 API
services/scripts/  # ScriptService 与演出脚本 API
```

Service 通过请求级只读 Player 判断内容可见性。需要写入玩家状态的操作必须使用命令回调和 EffectAction，而不能在 Service 的 GET 路由中直接执行。

## 5. Registry

- `registry/modules.py`：模块注册、视图回调和命令回调。
- `registry/files.py`：虚拟文件、路径、revision、内容和访问规则。
- `registry/scripts.py`：演出脚本、revision 和访问规则。

`main.py` 显式导入谜题模块并调用其 `register(registrar)`。所有 Registry 在应用启动时冻结；V2 当前允许显式注册列表为空。
