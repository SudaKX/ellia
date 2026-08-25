## Why

Markdown 图片当前只能直接写入完整 HTTP URL，导致内容绑定当前编辑器地址，也无法稳定表达文件管理器中的 UUID。需要在 Markdown 原文中保存可迁移的文件引用，并在预览阶段解析为当前编辑器可访问的文件 URL；本次先聚焦前端协议解析与复制入口，不启动导出实现。

## What Changes

- 约定 `ellia://file/<file_uuid>` 为 Markdown 文件引用格式，Markdown 原文只保存协议与文件 UUID，不保存编辑器的完整 HTTP 地址。
- 扩展 Markdown 预览渲染逻辑：识别 `ellia://file/<file_uuid>` 图片地址，在 `markdown-it` 图片 renderer 阶段解析为当前站点的 `/api/files/<file_uuid>` 完整访问 URL。
- 保持普通 `http`、`https` 和现有 Markdown 图片行为不变，并继续遵守 raw HTML 禁用与 Markdown 链接安全规则。
- 增加统一的文件引用/访问 URL 工具，避免 Markdown 渲染器与文件管理面板重复拼接 URL。
- 文件管理界面仅增加“复制 Markdown 图片引用”能力，复制形如 `![文件名](ellia://file/<file_uuid>)` 的 Markdown 文本；本次不做插入编辑器能力。
- 保证预览 URL 替换只发生在渲染阶段，编辑、保存和同步的 Markdown 原文保持 `ellia://file/<file_uuid>` 不变。
- 本次不实现导出、导出包内文件收集、UUID 到静态资源路径改写，也不修改服务端文件 API。

## Capabilities

### New Capabilities

- `markdown-file-references`: 定义前端 Markdown 中 Ellia 文件 URI 的格式、解析、预览渲染和文件引用复制行为。

### Modified Capabilities

- `markdown-editor`: 增加 Markdown 预览对 `ellia://file/<file_uuid>` 图片引用的支持，同时保持原文持久化和现有 Markdown 渲染约束。

## Impact

- 主要影响 `apps/web` 的 Markdown renderer、文件 URL/引用工具和文件管理面板。
- 可能新增前端单元测试或纯函数测试，用于 URI 解析、UUID 校验、URL 构造和图片 renderer 行为。
- 不新增 REST/WS 接口，不改变文件存储、实体同步或共享实体 schema；现有 `GET /api/files/:file_id` 直接作为图片预览端点。
- 导出器保持未实现状态；本 change 的验收范围不包含 Mythos 部署包或 Markdown 导出内容。
