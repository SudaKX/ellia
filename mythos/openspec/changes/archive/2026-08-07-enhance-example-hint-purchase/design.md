## Context

当前 `/example/` 是 FastAPI development 环境下挂载的静态页面，已经覆盖认证、Virtual Account、Progress、Files、Scripts 和 Validation，但 `example.js` 不读取 `/hints`，页面也没有 VTB 余额或 Hint 操作区域。

后端已经具备完整的 Hint 购买领域能力：`HintRegistry` 在启动期冻结，`HintService.disclose()` 在命令事务中 claim disclosure 并通过 `CreditInterface` 扣除 VTB，内容通过独立的预签名 URL 接口读取。玩家注册时会创建 `PlayerCredits`，但当前没有余额读取 API；新玩家默认余额为零。

本变更需要同时修改示例注册、只读 API、静态页面、测试和文档。实现必须遵守现有约束：静态内容在 Registry 冻结前注册，写入必须经过 `CommandTransactionExecutor`，模块不能自行提交 Session，也不能增加模块回调 HTTP 路由。

## Goals / Non-Goals

**Goals:**

- 在 example 模块中提供可购买、可揭示的真实 Hint 内容。
- 让 development/test 演示玩家获得有限且一次性的初始 VTB。
- 提供认证的 VTB 余额读取接口。
- 在 `/example/` 中完成 Hint 列表、购买、内容揭示、余额刷新和错误反馈。
- 覆盖购买成功、重复购买、余额不足、访问过滤和内容读取的后端验证，并提供中文浏览器手工验收清单。
- 保持 Hint 内容与文件树分离，并复用现有静态资源物化和对象存储流程。

**Non-Goals:**

- 不实现生产充值、支付或通用 VTB 发放 API。
- 不改变现有 `/api/v1/hints` 列表响应的余额契约。
- 不把 Hint 转换为 File 节点，也不把 Hint 正文通过 Mythos API 代理返回。
- 不实现 Hint 编辑、删除、价格动态配置或管理后台。
- 不要求为旧玩家补发初始 VTB。

## Decisions

### 1. 在 example 模块注册演示 Hint

在 `src/mythos/puzzles/example/__init__.py` 注册三个静态 Hint，并在 `assets/hints/` 下添加正文：两个 Hint 登录后可见，第三个使用现有 `example.completed` access rule，在完成 Echo 后出现。示例价格固定为 2、3、5 VTB，使用独立的 `HintDisplayParams`、`FileReference` 和安全下载名。

不把 Hint 加入 `assets/file-tree.json`，因为 Hint 有独立的 disclosure、价格、content token 和 access rule 生命周期。现有 `RegistryBundle.materialize_static_files()` 会把 FileRegistry 与 HintRegistry 的 sources 合并后一次性发布，新增资源不需要新的物化路径。

### 2. 通过生命周期回调提供演示余额

为 example 注册一个可配置的 `on_construct` 回调，在 development/test 演示模式下调用 `context.player.credits.grant_vtb(5)`。`AuthService` 会在 Construct 回调前创建 `PlayerCredits`，而 `on_construct` 受 `constructed_at` 保护，因此新玩家只会获得一次初始余额，且写入仍处于当前注册事务中。

由应用启动配置向 example 注册入口传递演示模式或初始余额，production 默认值为 0；不要通过新的 HTTP 端点发放余额。现有玩家不补发余额，测试购买流程使用新注册的玩家。

备选方案是把初始 VTB 写入 `/hints` 或增加开发充值按钮，但前者混淆资源与货币契约，后者会引入额外的可写 API 和安全边界，均不采用。

### 3. 新增独立的只读 Credits API

增加 `GET /api/v1/credits`，通过 `get_context(PlayerInterfaces.CREDITS)` 读取 `context.player.credits.vtb` 和 `version`，返回余额和余额版本。路由设置 `Cache-Control: no-store` 与 `Vary: Authorization`，并要求 Bearer Token。

不修改 `/api/v1/hints` 的响应结构。Hint 列表和余额在前端并行请求，购买完成后重新读取二者，以服务器状态作为唯一来源。

### 4. Example 页面采用 Hint 状态机

在 `example.js` 增加 credits、hints、selectedHint、hintPreview 和每项请求状态。认证、Virtual Account 切换、答案提交、全局刷新后并行加载 `/credits` 与 `/hints`。

每个 Hint 展示标题、teaser、媒体类型、大小、价格和状态：

```text
available -> purchasing -> disclosed -> revealing -> preview
                  |             |            |
                  +-- 409 -------+            +-- 412 -> refresh metadata
```

购买使用每次点击生成的新 `Request-ID`，调用 `POST /hints/{hint_id}/disclose`。成功后从响应更新 Hint 并重新加载余额；余额不足和不可用错误显示服务端 Problem Details。已购买 Hint 使用 `content_token` 调用 content-url 接口，再以现有文件 Preview 的方式读取预签名对象 URL。预签名 URL 只保存在内存，不写入持久化前端状态。

购买按钮在余额不足时不提前禁用，以便 example 页面能够真实触发并验证 `409 insufficient-credits`；请求进行中才禁用当前项。`HintService.list()` 会过滤不可用 Hint，因此 gated Hint 在满足条件后通过刷新列表出现，不额外扩展“锁定但不可见”的列表契约。

### 5. 以 API 集成测试和中文手工清单验证

后端沿用现有 `httpx.ASGITransport` 测试方式，验证注册、余额、列表、购买、重复购买、余额不足和内容 URL。浏览器交互由开发者手工访问 `/example/` 验证：新用户注册、显示余额、购买、揭示内容、完成 Echo 后出现 gated Hint，以及耗尽余额后的错误状态。手工验收不增加浏览器自动化依赖。

## Risks / Trade-offs

- [开发初始余额误进入生产] → 由启动配置显式区分 development/test 与 production，production 的 example 初始余额必须为 0，并增加配置测试。
- [旧数据库玩家无法立即购买] → 明确初始余额只对新 Construct 生效；浏览器验收使用新用户名，文档说明这一点。
- [示例 Hint 资源变化导致静态对象重新发布] → 使用现有 source digest 和 registration 复用机制，测试固定上传 key 与内容摘要行为。
- [并行刷新覆盖刚购买的前端状态] → 购买按钮按 Hint 粒度维护 pending 状态，成功后以购买响应和一次服务器刷新共同更新状态。
- [预签名 URL 暴露时间过长] → 不持久化 URL，复用现有 TTL、私有缓存策略和 `credentials: omit` 内容读取方式。
- [手工验收遗漏边界状态] → 后端自动化测试覆盖事务、幂等、余额不足和内容访问；文档清单覆盖页面主流程和错误分支。

## Migration Plan

1. 先注册示例 Hint、静态正文和 development/test 初始余额配置。
2. 增加 Credits 只读路由、测试和 API 文档。
3. 扩展 example 页面及其 CSS，并完成后端测试和中文手工验收清单。
4. 在新测试数据库上运行完整测试，再使用本地 development 服务手工检查 `/example/`。
5. 回滚时移除示例 Hint 注册、余额种子、Credits 路由和前端区域即可；不需要数据库降级或数据迁移。

## Open Questions

- 是否将 example 示例 Hint 在 production catalog 中完全排除，还是只禁止 production 初始 VTB，目前按现有 example 模块的全环境注册行为保留前者不变。
