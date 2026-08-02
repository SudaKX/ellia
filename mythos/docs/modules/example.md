# Example 模块

## 目的与边界

Example 是当前唯一由 `puzzles.register_all()` 注册的模块，用于验证认证、进度、静态文件、脚本、验证和 Artifact 的完整链路。它不拥有新的 HTTP Router、Service、SQL 表或 ORM Model；全部使用框架已有系统。

## 注册项与数据对象

| Registry | 注册内容 |
| --- | --- |
| progress | entry `example.entry`；checkpoint 节点 `example.completed` |
| files | `assets/file-tree.json` 中的 Public README 与受 completed 规则保护的 Archive result |
| artifacts | `example.recovery-report` 与 `/archive/recovery-report.txt` 节点 |
| scripts | `example.boot` answer-validator；受 completed 保护的 `example.completed` notice |
| validations | `example-answer` 对应 `example.answer.submit` handler |

验证 handler 的数据对象是 `CommandContext`、answer payload、`ValidationOutcome` 与 `RawArtifact`。Artifact 文本包含当前玩家 UUID，元数据保存 completed 节点 ID。

## HTTP 调用流

注册后，客户端读取 `/progress`、`/files/d/tree`、`/scripts`。提交正确答案到 `POST /validations/example-answer/attempts` 后，命令事务推进 progress、写 checkpoint、生成 Artifact。再读取动态树即可同时得到 `/archive/result.txt` 与 `/archive/recovery-report.txt`，后者通过通用文件 URL 端点取得预签名内容 URL。

## 测试与重要限制

`test_example_module.py` 使用 FakeObjectStore 验证端到端行为、`act2_` token、对象键和重复提交；`test_example_rustfs_integration.py` 在启用 RustFS 时读取真实预签名 URL。开发页面 `/example/` 使用动态树端点展示该流程。

模块 access rule 只读取 `player.progress.is_unlocked()`；模块不持有 Session、不能提交事务，不能添加回调路由。API 顺序见 [Example API 调用流](../api/example-flow.md)。
