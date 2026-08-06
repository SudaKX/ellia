# Example 模块

## 目的与边界

Example 是当前唯一由 `puzzles.register_all()` 注册的模块，用于验证认证、玩家生命周期、虚拟账号、进度、静态文件、脚本、验证和 Artifact 的完整链路。它不拥有新的 HTTP Router、Service、SQL 表或 ORM Model；全部使用框架已有系统。

## 注册项与数据对象

| Registry | 注册内容 |
| --- | --- |
| progress | entry `example.entry`；checkpoint 节点 `example.completed` |
| files | 无登录可见的 `/public`；仅 Administrator 可见的 `/admin/CONTROL.txt` |
| accounts | Guest 与 Administrator 模板；Construct 时发放 Guest |
| lifecycle | `on_construct` 发放固定 Guest 账号 |
| artifacts | `example.admin-access` 与仅 Guest 完成谜题后可见的 `/archive/ADMIN_ACCESS.txt` 节点 |
| scripts | Guest Echo 脚本、完成提示和 Administrator notice |
| validations | `example-answer` 对应 `example.answer.submit` handler |

验证 handler 的数据对象是 `CommandContext`、answer payload、`ValidationOutcome` 与 `RawArtifact`。Guest 通过 Echo 后，handler 发放 Administrator 账号并生成玩家专属管理员凭据文件。

## HTTP 调用流

注册事务中的 Construct 回调先发放 Guest。客户端从 `/public/GUEST_ACCESS.txt` 读取凭据并调用 `/vac/login`，才可看到 Echo 脚本并提交答案。Guest 完成 Echo 后，命令事务推进 progress、发放 Administrator、写 checkpoint、生成 `/archive/ADMIN_ACCESS.txt`。登录 Administrator 后可读取 `/admin/CONTROL.txt`。

## 测试与重要限制

`test_example_module.py` 使用 FakeObjectStore 验证端到端行为、`act3_` token、固定对象键和重复提交；`test_example_rustfs_integration.py` 在启用 RustFS 时读取真实预签名 URL，测试 bucket 不启用 versioning。开发页面 `/example/` 使用动态树端点展示该流程。

模块 access rule 读取 `player.accounts.is_current()` 与 `player.progress.is_unlocked()`；模块不持有 Session、不能提交事务，不能添加回调路由。API 顺序见 [Example API 调用流](../api/example-flow.md)。
