## 1. 文件引用基础工具

- [x] 1.1 新增前端文件引用工具，定义并严格解析 `ellia://file/<UUID>`，拒绝额外路径、query、fragment、非法 UUID 和其他自定义协议形态
- [x] 1.2 在同一工具中集中生成 Ellia 文件 URI、当前站点 `/api/files/<encoded UUID>` 访问 URL，以及带安全 alt 文本的 Markdown 图片引用
- [x] 1.3 为文件引用工具补充可验证的纯函数测试，覆盖合法 URI、非法 URI、UUID 编码、文件名回退和 Markdown 特殊字符场景

## 2. Markdown 图片预览解析

- [x] 2.1 扩展 Markdown renderer，在 `image` token 渲染阶段识别合法 `ellia://file/<UUID>` 并临时解析为当前文件 API URL
- [x] 2.2 保留 markdown-it 默认图片渲染行为，包括 alt/title 处理、属性转义、普通 HTTP/HTTPS/相对路径兼容和 raw HTML 禁用
- [x] 2.3 为非法 Ellia 图片引用提供不发起任意网络请求的安全失败/占位表现，并确保 renderer 不污染后续渲染或修改输入 Markdown
- [x] 2.4 验证 Markdown 预览调用方（MarkdownEditor、QuestionnaireEditor、QuestionCard）均通过共享 renderer 获得 Ellia 图片解析能力
- [x] 2.5 增加 Markdown renderer 行为测试，覆盖合法 Ellia 图片、普通图片、非法 URI、alt/title 保留、重复渲染和原文不变

## 3. 文件管理器复制入口

- [x] 3.1 在文件管理器选中文件详情操作区增加“复制 Markdown 图片引用”按钮，并复用统一引用生成工具
- [x] 3.2 复用现有复制成功状态与错误反馈，处理 Clipboard API 失败；复制动作不得触发实体或同步状态修改
- [x] 3.3 验证有原始文件名和无原始文件名两种情况下复制内容分别使用文件名和 UUID 作为 alt 文本，并保留文件 UUID

## 4. 集成验证与范围检查

- [x] 4.1 运行 editor 类型检查与前端构建，确认新增工具、renderer 和文件管理器改动通过 TypeScript/Vue 校验
- [x] 4.2 通过 renderer 输出测试与现有登录态文件 API 回归测试验证预览使用 `/api/files/<UUID>`，非法/失效引用不产生任意协议请求
- [x] 4.3 确认 Markdown 保存/WS patch 的内容仍为 `ellia://file/<UUID>`，且本 change 未引入导出实现、服务端 API 修改或编辑器自动插入能力
