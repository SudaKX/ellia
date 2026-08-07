# Mythos API 对接

所有业务 Router 使用 `/api/v1` 前缀；`GET /health` 不在此前缀下。除注册、登录、refresh 和健康检查外，调用都需要 `Authorization: Bearer <access token>`；refresh 使用 HttpOnly refresh cookie。对象存储预签名 URL 不携带 Bearer header，前端必须先向 Mythos 获取 URL，再直接请求对象存储。

| 契约 | 说明 |
| --- | --- |
| [认证](authentication.md) | token、refresh cookie、会话恢复 |
| [命令](commands.md) | Request-ID、命令响应和 followups |
| [进度](progress.md) | 进度投影和 checkpoint restore |
| [文件](files.md) | 静态/动态树、metadata、预签名 URL |
| [脚本](scripts.md) | 可见脚本 DTO |
| [验证](validations.md) | 模块 validation 提交 |
| [VirtualAccount](virtual-accounts.md) | 玩家虚拟账号登录和登出 |
| [错误与缓存](errors-and-caching.md) | 跨端点恢复策略 |
| [Example 流程](example-flow.md) | 开发页面调用顺序 |

本目录不描述 SQL、ORM、Registry 或模块 handler 实现；这些信息在对应的 `systems/` 文档中维护。
