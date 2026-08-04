# Mythos 后端文档

本文档集以当前 `src/mythos/` 实现为准。领域文档解释持久化、Registry 和运行机制；`api/` 仅定义前后端 HTTP 契约；`archive/` 保留历史设计，不能作为当前实现依据。

## 架构

- [运行时组装](architecture/runtime-and-composition.md)
- [Player 与请求上下文](architecture/player-and-request-context.md)
- [命令事务](architecture/command-transactions.md)
- [错误响应与中间件](architecture/error-response-and-middleware.md)
- [持久化总览](reference/persistence-schema.md)

## 领域系统

- [认证](systems/authentication.md)
- [进度与 checkpoint](systems/progress-and-checkpoints.md)
- [静态文件与对象存储](systems/files-and-object-storage.md)
- [Artifact 与动态文件](systems/artifacts-and-dynamic-files.md)
- [脚本](systems/scripts.md)
- [验证](systems/validations.md)

## API 对接

- [API 索引](api/README.md)
- [认证契约](api/authentication.md)
- [命令契约](api/commands.md)
- [进度契约](api/progress.md)
- [文件契约](api/files.md)
- [脚本契约](api/scripts.md)
- [验证契约](api/validations.md)
- [错误与缓存](api/errors-and-caching.md)
- [Example 调用流](api/example-flow.md)

## 模块与运维

- [Example 模块](modules/example.md)
- [开发与存储运行](operations/development-and-storage.md)

## 维护规则

- 修改 Model、Router、Registry、Interface 或 Example 行为时，同一变更必须更新对应领域文档与 API 契约。
- API 文档不得描述未由当前 Router 暴露的端点；领域文档必须显式说明不存在的表、Interface、Service 或端点。
- 新模块只通过既有 Registry 和语义化端点接入，不能新增通用 callback 路由。
