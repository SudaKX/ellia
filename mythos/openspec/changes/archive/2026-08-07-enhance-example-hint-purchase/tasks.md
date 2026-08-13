## 1. 示例 Hint 与演示余额

- [x] 1.1 在 `src/mythos/puzzles/example/assets/hints/` 增加三个用于演示的文本 Hint 资源，并确定其非剧透标题、teaser、下载名和媒体类型。
- [x] 1.2 在 example 注册函数中注册两个公开 Hint 和一个以 `example.completed` 为 access rule 的 gated Hint，价格分别为 2、3、5 VTB。
- [x] 1.3 为 example 注册 development/test 专用的 Construct 初始余额回调，向新玩家发放 5 VTB，并确保 production 不自动发放。
- [x] 1.4 更新 example 相关静态资源物化和模块测试的预期，确认 Hint sources 与现有 File sources 一起发布且不进入文件树。

## 2. Credits 只读 API

- [x] 2.1 新增认证的 `GET /api/v1/credits` router，使用只读 `PlayerInterfaces.CREDITS` 上下文返回 `vtb` 和 `version`。
- [x] 2.2 为 Credits 响应设置 `Cache-Control: no-store`、`Vary: Authorization`，并在应用入口挂载 `/api/v1` 路由。
- [x] 2.3 增加 API 测试，覆盖有效认证、匿名拒绝、购买成功后的余额/版本变化和余额不足后的事务不变性。

## 3. Example Hint 交互界面

- [x] 3.1 在 `example/index.html` 增加 Hints 区域、VTB 余额显示、Hint 列表、Purchase/Reveal 控件和 Hint 内容预览容器。
- [x] 3.2 在 `example/example.css` 增加 Hint 列表、价格、购买状态、加载状态、成功状态和错误状态样式，并保持现有桌面、窄屏和移动布局不重叠。
- [x] 3.3 扩展 `example/example.js` 状态模型和 workspace 清理逻辑，管理 credits、hints、选中 Hint、预览内容及每项请求状态。
- [x] 3.4 在认证、Virtual Account 切换、答案提交成功和全局 Refresh 流程中并行加载 `/credits` 与 `/hints`，并将 gated Hint 的出现绑定到刷新结果。
- [x] 3.5 实现 Purchase 请求，为每次点击生成新的 `Request-ID`，处理成功、重复购买、`insufficient-credits`、`hint-unavailable` 和网络错误状态。
- [x] 3.6 实现 Reveal 请求和预签名对象读取，复用现有内容预览模式，处理 `412 hint-content-version-mismatch` 时刷新元数据并最多重试一次。
- [x] 3.7 将 Hint 请求纳入现有 Requests 事件列表，确保增加 Hint 功能不破坏原有认证、文件、Progress、Scripts 和 Validation 交互。

## 4. 测试与文档

- [x] 4.1 扩展 `tests/test_example_module.py`，验证新玩家初始 VTB、Hint 列表、公开/gated 可见性和静态 Hint 对象发布。
- [x] 4.2 扩展 `tests/test_hints.py` 或新增聚焦测试，验证示例 Hint 的成功购买、重复购买、余额不足回滚、content-url 和内容读取。
- [x] 4.3 编写中文浏览器手工验收清单，覆盖 `/example/` 注册、显示余额、购买、Reveal、gated Hint 和余额不足错误流程。
- [x] 4.4 更新 `docs/api/hints.md`、`docs/api/example-flow.md`、`docs/modules/example.md`，使用中文记录 Credits API、Hint 交互顺序、初始余额限制和测试方式。
- [x] 4.5 按仓库指南运行完整后端测试、JavaScript/Python 静态检查，确认 development 与 production 配置的初始余额行为符合规格，并记录浏览器手工验收入口。
