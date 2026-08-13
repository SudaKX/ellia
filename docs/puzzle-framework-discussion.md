# 谜题共创框架 — 设计讨论稿

> 本文是给开发者讨论用的设计草案，不是最终规范。目标：让**不同的人**能独立、低门槛地共创**各种类型**的谜题，并且能接入现有 `mythos` 后端与 `desktop` 前端的进度/文件/脚本体系。文中的「开放问题」段是讨论重点，尚未定论。

## 1. 目标与范围

- **多作者共创**：作者不应该需要理解后端整体架构，只需按模板产出“一个谜题包”。
- **多类型适配**：从简单的“输入答案”到「凯撒密码」「二进制网格」这类图形题，再到 Live2D 演出、甚至 Godot/WebGL 小游戏，都要有统一挂载方式。
- **简化流程**：尽量“填声明 + 放素材”，少写代码；服务端权威状态、进度、文件解锁、checkpoint 全部复用现成体系。

## 2. 现状盘点（可复用基础）

### 后端 `mythos` 已有

- `example` 模块是唯一谜题范例，已演示完整闭环：静态文件 → 答案校验 → 进度推进 → checkpoint → 解锁新文件。
- 五类 Registry 已是通用挂载点：`files`（静态树/Artifact）、`progress`（节点图）、`scripts`（演出脚本）、`validations`（答案判定）、`artifacts`（玩家专属文件）。
- 命令协议已固定：`Request-ID` 幂等、统一 `{content, followups}` 响应、`accepted:false` 仍返回 `200`。
- 注册方式是**显式 Python 代码**（[puzzles/__init__.py](file:///f:/codes/web_game/ellia/mythos/src/mythos/puzzles/__init__.py) 逐个 `register()`）。

### 前端 `desktop` 已有

- 谜题注册表 [registries/puzzles.ts](file:///f:/codes/web_game/ellia/desktop/src/registries/puzzles.ts)：`id + i18n key + Vue 组件 + 窗口尺寸`，`sil <id>` 命令与文件资源管理器双击 `.puz` 均走此注册表。
- `usePuzzle`：目前是 **localStorage 本地判定**（尚未接后端），有 `state/hints/reset` 等通用 API。
- 已出现多种交互形态，可作为类型划分依据：

| 类型 | 代表实现 | 交互形态 |
| --- | --- | --- |
| 文本答题 | `ExampleCipher.vue`（caesar-cipher） | 表单输入答案 |
| 本地引擎/步骤 | `useLockPuzzle` | window 上藏函数、分步调用、本地状态机 |
| 网格/图形 | `binary-grid`（mock 数据中出现） | 图形网格操作 |
| 视觉呈现 | `AsciiFlow` | canvas 渲染、观赏型 |
| 演出/角色 | `Live2DAssistant` | Live2D 角色互动 |
| 系统探索 | 终端命令 + 文件系统 | CLI/文件线索，通常作为其他谜题的前置线索载体 |

## 3. 谜题类型谱系（适配的目标集合）

把谜题按「渲染形态 × 验证方式」两个维度分类，框架据此分派渲染器：

```
渲染形态
├─ 表单型     → 通用答题组件（后端 answer-validator 脚本驱动，零新代码）
├─ 自绘型     → 作者写一个 Vue 组件（canvas/SVG/DOM 均可）
├─ 剧本演出型 → 脚本/素材驱动（notice、对话、Live2D 动作用于表达，不负责判定）
└─ 引擎嵌入型 → 外部引擎导出（Godot/Unity/WebGL），iframe 嵌入

验证方式
├─ 服务端判定   → validation_id + payload，后端权威校验（文本/网格/数值）
├─ 客户端判定   → 引擎/组件内部判定，通关后只上报“结果事件 + 一次性凭据”
└─ 无强验证     → 演出/探索类，只随进度解锁内容
```

> 关键原则：**权威状态永远在服务端**。客户端/引擎内可以自由判断，但“通关”这一事实必须通过 `validations` 提交到后端，进度与 Artifact 才被推进。

## 4. 框架总体设计（四层）

```
① 描述层    puzzle.yaml（一个谜题包 = 一份描述 + 素材目录）
② 注册/权威层  后端自动加载器：描述 → 五类 Registry；服务端校验/进度/文件
③ 渲染/交互层  前端按 kind 分派渲染器：通用表单 | 自定义组件 | 引擎 iframe
④ 引擎适配层   Godot 等外部引擎 ←postMessage 桥→ 前端宿主 ←REST→ 后端
```

### 4.1 描述层：`puzzle.yaml`

作者产出“一个谜题包”，通用字段 + `kind` 专属字段：

```yaml
id: caesar-cipher
kind: answer-form            # answer-form | custom | engine | scripted
titleKey: puzzles.caesarCipher.title
version: 1
window: { width: 520, height: 400 }

# 服务端部分（可缺省，缺省则只做展示型/引擎型）
progress: { entry: "caesar.entry", completes: "caesar.completed", checkpoint: true }
files:
  - path: /puzzles/caesar-cipher/README.txt
    source: assets/public/README.txt
    access: public
  - path: /archive/flag.txt
    access: completed
validations:
  - id: caesar-answer
    validator: normalize-case
    expected: "hello world"
scripts:
  - kind: answer-validator
    validation_id: caesar-answer
    input: { name: answer, label: "Shifted text" }

# 引擎嵌入型专属
engine: { runtime: godot-4, entry: "index.html", width: 800, height: 600 }
```

### 4.2 注册/权威层：后端自动加载器

- 新增 `load_puzzle_package(puzzle_dir)`：读 yaml → 自动调用五类 Registry → 启动期校验。
- `puzzles/__init__.py` 不再需要作者手写注册代码；作者只需在目录注册表里加一行（或按约定扫描 `puzzles/packages/<id>/`）。
- 保留 `hooks.py` 逃生口：自定义 validator / Artifact generator / 复杂进度逻辑仍可写 Python，覆盖 20% 特殊谜题。

### 4.3 渲染/交互层：前端按 `kind` 分派

- `puzzles.ts` 注册表从“作者手写组件”演进为“描述驱动”：
  - `answer-form` → 通用 `PuzzleAnswerForm.vue`（读 `/scripts` 的 `answer-validator` body 自动渲染输入框/提示/提交），**作者零 Vue 代码**；
  - `custom` → 作者提供组件，只实现一个约定接口（见 5.2）；
  - `engine` → 统一 `EnginePuzzleHost.vue`（iframe + 通信桥）；
  - `scripted` → 走现有脚本/演出组件。
- 通关后统一调用 `usePuzzle.submitResult(puzzleId, resultPayload)`（内部带 `Request-ID` 调后端 validation；无服务端 validation 的演出/探索型走进度接口）。

### 4.4 引擎适配层：Godot 等外部引擎桥接

外部引擎（Godot 4 导出 Web、Unity WebGL、自研 canvas 游戏）通过 iframe 嵌入，协议建议：

```text
引擎(iframe) ──postMessage──▶ 前端宿主(EnginePuzzleHost)
  { type:'puzzle', event:'ready' }                 // 引擎加载完成
  { type:'puzzle', event:'solved', nonce:'xxx' }   // 通关上报（一次性凭据）
  { type:'puzzle', event:'hint-requested' }

前端宿主 ──postMessage──▶ 引擎
  { type:'host', event:'reset' }                   // 重开/重置
  { type:'host', event:'progress', state:{...} }   // 进度同步（如已通关禁止重复提交）

前端宿主 ──REST──▶ 后端
  POST /validations/{id}/attempts  （Request-ID + nonce → 服务端二次确认）
```

- **为什么用 nonce/一次性凭据**：引擎 iframe 内部不应持有用户 token；通关事件由宿主带 Bearer 提交，`nonce` 防止重放（引擎每次通关生成一次性的 challenge，服务端校验后作废）。
- 引擎只负责“玩”，不负责“存”；进度、文件解锁、成就全走后端。

## 5. 简化开发流程的配套

| 配套 | 说明 |
| --- | --- |
| 脚手架 | `python -m mythos new-puzzle <id> --kind <type>` 生成目录 + yaml 模板 + i18n key + 注册行 |
| 标准校验器库 | `exact / normalize-case / regex / multi-answer / numeric / grid` 等插件化判定器，输出统一 `accepted:bool` |
| 启动期 Lint | 重复 stable_id、文件 source 缺失、进度边断裂、access_rule 引用未知 ID、yaml schema 错 → 拒绝启动 |
| 自动集成测试 | 按描述自动生成：注册成功 → 解锁前文件不可见 → 提交正确答案 → 解锁后可见 + checkpoint 落盘 |
| 素材与 i18n 约定 | 素材放 `assets/`；文案 key 自动按 `puzzles.<id>.*` 生成，语言包由作者补充或众包 |
| 文档模板 | 《谜题创作指南》以 `example` + 一个新脚手架生成的谜题为双范例 |

## 6. 关键设计决策与开放问题（讨论重点）

1. **描述优先还是代码优先**：建议 yaml 描述覆盖 80%（常规答题/图形/引擎嵌入），Python hooks 保留给演出/动态。反对一上来就做“零代码 DSL”到极致，避免过度设计。
2. **本地引擎型（如 lockPuzzle）如何对接服务端**：服务端是否**只保存完成状态**（不重复实现其内部逻辑），还是把分步逻辑也搬到后端？倾向：客户端保留玩法，服务端只收最终结果，减少重复实现。
3. **引擎桥接协议是否够用**：Godot 导出后资源/尺寸/输入焦点、以及暂停/恢复（窗口最小化）如何处理？是否需要 `progress` 双向同步事件？
4. **nonce 机制与防作弊边界**：纯客户端谜题本来就能被破解，nonce 只防重放；演出类谜题是否根本不校验（只做展示）？
5. **版本与发布**：谜题内容更新用 `version` 字段 + 幂等发布；已通关玩家的 Artifact/文件缓存如何处理？
6. **审核与测试**：自动 Lint 只查结构，交互质量/平衡性是否需要人工 review 清单？
7. **Godot 等引擎的引入成本**：引擎谜题不能直接读 `desktop` 的组件/样式，视觉效果一致性如何约束？是否定一个最小 UI 规范（字体/配色 token）通过 postMessage 下发？

## 7. 建议里程碑

| 阶段 | 交付 | 说明 |
| --- | --- | --- |
| M0 | 官方模板固化 | 把 `example` 整理成唯一范例 + 编写《谜题创作指南》 |
| M1 | 脚手架 + 启动期 Lint | `new-puzzle` 生成器 + 加载期校验，普通作者可独立产出 |
| M2 | 声明式加载 + 自动测试 | yaml → 五类 Registry 自动注册；按描述生成集成测试 |
| M3 | 引擎桥接 | `EnginePuzzleHost` + postMessage 协议 + 一个 Godot 示例谜题验证全链路 |

## 相关链接

- 后端模块范例：[mythos/src/mythos/puzzles/example](file:///f:/codes/web_game/ellia/mythos/src/mythos/puzzles/example)
- 后端五类 Registry：`mythos/src/mythos/registry/{files,progress,scripts,validations,artifacts}/`
- 前端谜题注册表：[desktop/src/registries/puzzles.ts](file:///f:/codes/web_game/ellia/desktop/src/registries/puzzles.ts)
- 前端谜题 API：[desktop/src/composables/usePuzzle.ts](file:///f:/codes/web_game/ellia/desktop/src/composables/usePuzzle.ts)
- 前后端对接约束：[desktop/docs/backend-integration.md](file:///f:/codes/web_game/ellia/desktop/docs/backend-integration.md)
