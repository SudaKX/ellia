# Commit 规范

所有提交信息使用以下格式：

```text
type(module): description
```

如需补充修改细节，可在标题后空一行，以 Markdown 无序列表列出简短的修改点：

```text
feat(console): 添加窗口最小化功能

- 在状态栏显示已最小化窗口
- 支持点击状态栏恢复窗口
```

## 字段说明

- `type`：本次修改的类别，使用小写英文。
- `module`：受影响的模块或目录，使用小写英文；多个模块用逗号分隔。
- `description`：简洁说明本次修改，使用中文或英文均可，不使用句号结尾。

## Type

| Type | 说明 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档修改 |
| `style` | 不影响逻辑的代码格式或样式调整 |
| `refactor` | 不新增功能也不修复缺陷的代码重构 |
| `test` | 测试新增或调整 |
| `chore` | 构建、依赖、配置或其他维护性修改 |
| `perf` | 性能优化 |
| `ci` | CI/CD 配置修改 |

## 示例

```text
feat(console): 添加窗口最小化功能
fix(api): 修复玩家进度保存失败的问题
docs(root): 添加 commit 规范
refactor(puzzle,api): 提取谜题答案校验逻辑
chore(deps): 升级 FastAPI 依赖
```

## 要求

- 每个提交只聚焦一个明确目的。
- `description` 使用祈使语气，准确描述改动内容。
- 详细修改点为可选内容，使用 Markdown 无序列表；每点保持简短，只描述一项改动。
- 提交前确保代码、测试和相关文档处于可用状态。
