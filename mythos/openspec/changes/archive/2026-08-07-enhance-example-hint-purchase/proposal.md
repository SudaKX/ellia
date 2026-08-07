## Why

`/example/` 当前可以演示认证、虚拟账号、进度、文件和验证流程，但无法演示后端已经具备的 VTB 购买 Hint 能力。开发者只能通过 `tests/test_hints.py` 以 API 集成测试验证购买流程，无法在浏览器中观察余额变化、购买状态和 Hint 内容展示。

现在补齐这条链路，可以让 example 页面成为可重复使用的端到端开发验证入口，同时继续保持 Hint、文件和玩家事务边界清晰。

## What Changes

- 为 example 模块增加用于演示的 Hint 内容、价格和静态资源。
- 在开发/测试演示场景为新玩家提供一次性的初始 VTB，支持成功购买和余额不足两种路径。
- 增加认证的只读 VTB 余额接口，供 example 页面展示当前余额。
- 在 `/example/` 增加 Hint 列表、购买、内容揭示、余额刷新和错误状态交互。
- 在登录、虚拟账号切换、答案提交和全局刷新后同步刷新 Hint 与余额状态。
- 增加后端集成测试、中文手工验收步骤和相关 API/Example 文档。
- 不增加通用充值接口，不把预签名内容 URL 持久化到前端状态，不修改现有文件树语义。

## Capabilities

### New Capabilities

- `example-hint-playground`: 提供示例 Hint 注册、演示用 VTB 初始余额、浏览器端购买和内容揭示流程。
- `credits-read-api`: 提供认证玩家读取当前 VTB 余额和余额版本的只读 API。

### Modified Capabilities

- 无。当前 `openspec/specs/` 没有已存在的能力规格。

## Impact

- 后端：example puzzle 注册、生命周期种子、credits router、路由挂载和 Hint 相关集成测试。
- 前端：`example/index.html`、`example/example.js`、`example/example.css` 的状态、请求和预览交互。
- 静态资源：新增 example Hint 源文件，由现有静态资源物化流程发布。
- 文档：Hint API、Example API 调用流和 Example 模块说明。
- 数据库：复用现有 `player_credits`、`player_hint_disclosures` 和静态文件登记表，不需要新增迁移。
- 验收方式：后端自动化测试负责 API 和事务行为，浏览器交互由开发者按中文手工清单验收。
