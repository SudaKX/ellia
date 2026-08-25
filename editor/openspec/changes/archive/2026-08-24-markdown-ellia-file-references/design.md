## Context

当前 `apps/web` 的 Markdown 预览统一经过 `panes/markdown/render.ts` 中的 `markdown-it` 实例，并由多个预览组件通过 `v-html` 使用结果。文件管理器已经通过 `GET /api/files/:file_id` 提供登录态下的原始文件访问，但访问 URL 拼接目前局部存在于文件管理面板。`.ref/markdown-it` 已提供 `renderer.rules.image` 覆盖点，因此不需要修改 markdown-it 源码或引入新的 Markdown 语法解析器。

本 change 的规范细节见 `specs/markdown-file-references/spec.md` 与 `specs/markdown-editor/spec.md`。导出器仍处于 M3 占位状态，不参与本设计。

## Goals / Non-Goals

**Goals:**

- 为前端建立严格、可复用的 `ellia://file/<UUID>` 解析与生成规则。
- 在 MarkdownIt 的 image renderer 层把合法 Ellia 文件 URI 转换为当前站点的文件 API URL。
- 让 `MarkdownEditor`、问卷 Markdown 说明等所有复用 `renderMarkdown()` 的预览自动获得同样能力。
- 让文件管理器复制稳定的 Markdown 图片引用，并明确复制状态和失败反馈。
- 保持安全边界：只解析合法 UUID，不把任意自定义协议变成网络请求目标。

**Non-Goals:**

- 不修改 server 文件路由、鉴权或文件存储数据模型。
- 不实现 Markdown 编辑器中的文件选择/插入按钮。
- 不实现导出、导出包文件收集、静态资源路径改写或 Mythos 运行时的 `ellia://` 解析。
- 不支持 `ellia://` 作为通用链接协议；本 change 只处理图片 destination 中的 `ellia://file/`。

## Decisions

### 1. 使用 `ellia://file/<UUID>` 作为唯一规范格式

文件 UUID 当前已经是服务端 files 表主键和磁盘对象名，使用自定义协议可以把“Ellia 文件引用”与普通相对路径区分开。协议路径只允许一个 `file` 类型段和一个标准 UUID，不接受 query、fragment、额外路径段或任意文件名。

考虑过裸 UUID 识别，但它会与普通相对图片路径和未来的文件名产生歧义，因此不作为规范格式；实现阶段无需对裸 UUID 做隐式兼容。

### 2. 将协议解析、URL 生成、Markdown 引用生成集中到一个前端工具

建议在 `apps/web/src/utils` 或 Markdown 相关目录新增纯工具模块，提供三类职责：

- 解析并校验 Ellia 文件 URI，成功返回文件 UUID，失败返回空结果。
- 根据文件 UUID 生成当前站点的 `/api/files/<encoded_uuid>` 访问 URL。
- 根据展示名称和 UUID 生成 `![alt](ellia://file/uuid)` 文本。

文件管理器和 renderer 都使用同一套工具，避免一个地方接受宽松格式、另一个地方接受严格格式。访问 URL 应使用当前浏览器 origin 与同源 `/api` 路径，保持开发环境 Vite 代理和生产部署路径一致；UUID 作为 URL 路径段必须编码。

### 3. 覆盖 `renderer.rules.image`，不修改 Markdown 原文

初始化 MarkdownIt 后保存原有 image renderer，然后注册一个包装规则：

1. 读取 image token 的 `src`。
2. 仅当解析器确认它是合法 Ellia 文件 URI时，将 token 的 `src` 临时替换为文件 API URL。
3. 委托原有 image renderer 生成 HTML，保留 markdown-it 对 alt/title 的处理和属性转义。
4. 不把 token 修改结果写回 segment、questionnaire 或其他实体 state。

为了避免响应式调用之间共享 token 产生副作用，包装规则应尽量只在一次 renderer 调用期间修改并恢复 `src`，或对 attrs 做局部副本后交给默认 token 渲染逻辑。普通图片 destination 走原有 renderer。

### 4. 非法 Ellia 图片不发起请求，并使用安全的失败表现

不能把 malformed `ellia://file/...` 交给浏览器，也不能把 URI 原样输出为 `<img src>`。设计上应让 renderer 为此类 token 生成不指向网络的失败/占位图片表达，并保留可读的 alt 文本；实现可使用空的安全 `src` 或专用占位标记，但必须避免触发当前页面、任意协议或任意域名请求。该表现不影响原始 Markdown 保存。

### 5. 文件管理器只提供复制 Markdown 图片引用

`FileManagerPanel.vue` 在选中文件详情操作区新增“复制 Markdown 图片引用”。按钮调用统一引用生成工具并写入 Clipboard API；成功时复用现有短暂“已复制”反馈，失败时显示错误信息。原有“复制访问链接”可继续保留，两者用途不同：前者复制稳定 Markdown source，后者复制当前环境的直接访问 URL。

本次不向 `MarkdownCodeEditor` 暴露 CodeMirror 实例，也不增加跨组件插入协议；复制动作不触发 WS patch 和任何实体更新。

### 6. 测试边界覆盖纯函数与实际 renderer 行为

优先为 URI parser、URL/reference builder 编写纯函数测试，再对 Markdown renderer 验证：合法 Ellia URI 被替换、普通图片不受影响、非法 URI 不产生任意网络 src、alt/title 保留、原始输入字符串不变。文件管理器的复制动作至少通过组件测试或可测试的生成函数覆盖命名文件和无名称文件两种情况。

## Risks / Trade-offs

- **[Risk] 文件被手动删除后，Markdown 仍保留 UUID，预览会出现失效图片。** → 保持文件系统现有“允许悬空引用”语义；预览只显示浏览器/占位失败，不自动修改 Markdown 或删除引用。
- **[Risk] `<img>` 请求需要登录 Cookie，跨域部署时可能无法直接加载。** → 本 change 只支持当前站点同源 `/api/files`；跨域或匿名资源访问留给后续文件服务设计，不在本次通过 CORS 或 token URL 绕过。
- **[Risk] markdown-it renderer token 是可变对象，错误的临时修改可能污染后续渲染。** → 包装 renderer 应使用局部 attrs 或严格的 try/finally 恢复 `src`，并用重复渲染测试确认同一输入不会产生环境 URL 泄漏。
- **[Risk] Clipboard API 在非安全上下文或权限拒绝时失败。** → 捕获异常并显示现有错误反馈；生成 Markdown 引用的纯函数仍可独立测试，不依赖 Clipboard API。
- **[Risk] 未来导出需要把 Ellia URI 映射到静态文件路径。** → 本次明确不实现导出，保留原始 URI 作为稳定编辑格式；未来导出设计必须读取原文而非预览 HTML。
