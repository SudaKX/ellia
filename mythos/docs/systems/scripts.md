# 脚本系统

## 数据和 Registry

脚本没有 SQL 表、ORM Model 或 Player Interface。模块注册不可变 `Script(stable_id, revision, body, access_rule)`；`ScriptRegistry` 冻结为 `ScriptCatalog`，后者用 access rule 过滤当前玩家可见脚本。

`body` 是未由后端强制固定 schema 的 JSON 映射；`ScriptService` 仅复制为 `{stable_id, revision, body}`。调用方须按 `body.kind` 解释其字段，且脚本 revision 应在语义变化时递增。

## Service 与端点

`ScriptService.visible(player)` 是全局 Service；`GET /api/v1/scripts` 通过只读 progress Context 返回可见项目。它没有写入端点、命令、数据库副作用或专属 token。API DTO 见 [脚本契约](../api/scripts.md)。

## Example 与约束

Example 注册始终可见的 `example.boot`，其 `answer-validator` body 提供 validation ID、输入字段与提示文本；完成后可见 `example.completed`，其 body 是 `notice`。脚本 access rule 必须是纯 Player 读取函数，不能修改进度或调用外部服务。

相关实现：`registry/scripts/`、`services/scripts/`。
