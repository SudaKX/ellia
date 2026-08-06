---
name: "fakeos-story-writer"
description: "Converts plain-text story drafts (dialogue, branches, sliders) into runnable FakeOS story windows: generates a StoryNode[] script, registers it, and adds a clickable story file in the virtual filesystem. Invoke when a writer (non-coder) wants to turn their narrative into a playable story in the web desktop."
---

# FakeOS Story Writer（文案转剧情窗口）

把**自然语言剧情文案**转成 **FakeOS 网页里可以玩的剧情窗口**：生成剧情脚本、注册进系统、在虚拟文件系统放一个"可执行剧情文件"（类似 `init.exe`），玩家在网页文件资源管理器里**双击该文件就能播放这段剧情**。

使用者（文案创作者）只需要提供剧情文字，**全程不用写代码**；开发者只需 `pnpm dev` 或提交代码。

---

## ⭐ 最重要的原则：先问，再动手（不许自作主张）

本 skill 的**使用者是不懂代码的文案创作者**。因此：

1. **全程用大白话**。不要对用户抛代码、不要甩技术名词（比如"StoryNode""storyId""i18n"）。用户只需要理解"你的剧情会有哪些对话、玩家能选什么"。
2. **先读、先复述、先问，最后才动手**。AI 拿到文案后，第一步不是写代码，而是：
   - 用自己的话**复述一遍剧情**给用户听（谁和谁对话、玩家会经历什么、有哪些分支），让用户确认"你说的是不是这个意思"。
   - 把**不确定的地方**问清楚（下面有清单）。
   - **用户确认后才开始生成**。
3. 每个关键决定（文件叫什么名、放在哪个文件夹、选项怎么设计、要不要成就）都**先问用户**，让用户拍板。
4. 如果用户给的文案里有占位符（如"xxx"）、没说清楚的地方、或明显冲突的内容，**不要自己脑补补全**，要停下来问。

---

## 一、开始之前：先复述，把话说清楚

拿到文案后，先用一段大白话向用户复述你读到的内容，例如：

> "我理解你的剧情是这样的：开头是 JDK 学姐欢迎玩家，然后 Ellia 出场问你'你想做什么'，你有三个选项——看文件 / 问身份 / 保持沉默，选不同的会走向不同的对话；中间还有个'信任程度'的滑杆，拉得高和拉得低结局不一样。是这样吗？"

用户说"对"，再进入下一步。**用户还没确认前，不要开始改任何文件。**

## 二、动手前必问清单（用大白话逐条问）

按需向用户提问（不要一次抛太多，按剧情情况挑相关的）：

| # | 大白话问题 | 为什么问 |
| --- | --- | --- |
| 1 | 这个剧情文件你想叫什么名字？（比如"init.exe""开始演出.exe"） | 决定虚拟文件系统的文件名 |
| 2 | 想把它放在网页桌面的哪个文件夹里？（默认可以放"home"文件夹，和 init.exe 放一起） | 决定放哪个目录 |
| 3 | 剧情开场是谁先说第一句话？大概什么内容？ | 确认起点 |
| 4 | 玩家在哪些地方需要做选择？每个选择有几个选项？（记住：一次最多 4 个选项） | 决定分支结构 |
| 5 | 有没有"拉杆/调数值"的环节？（比如信任度 0~100，拉高拉低走向不同） | 决定滑杆 |
| 6 | 选不同选项之后，剧情各走向哪？分别是什么结局/台词？ | 确认分支目标 |
| 7 | 这段剧情要不要弹成就（右下角那种）？要的话成就叫什么名字、配什么图/音效？ | 决定成就 |
| 8 | 文案里有没有你没看懂、或者想让我补全的地方？ | 消除歧义 |

> 用户答不上来或说"你看着办"的项，你才能自行决定，并**用一句话告诉用户你做了什么决定**。

## 三、（AI 内部）剧情脚本规则

> 以下内容是 AI 写代码时用的规则，**不需要讲给用户听**。

```ts
import type { StoryNode } from '@/composables/useStoryDialog'

const script: StoryNode[] = [
  { id: 'welcome', speaker: 'JDK', text: '欢迎来到【FAKE_OS】。', next: 'ask' },
  {
    id: 'ask', speaker: 'E', text: '你想做什么？',
    choices: [                                  // 选项：最多 4 个
      { label: '看看文件', next: 'files' },
      { label: '你是谁', next: 'who' },
    ],
  },
  {
    id: 'trust', speaker: 'E', text: '你信我吗？',
    slider: {                                   // 滑杆调节
      label: '信任程度', min: 0, max: 100,
      next: (v) => (v >= 70 ? 'high' : 'low'),  // 按数值分叉
    },
  },
  { id: 'files', speaker: 'E', text: '那去找一份叫"看这里看这里"的文件。' },
]
```

### 字段与硬性约束

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `id` | 节点唯一 id（跳转目标） | 可省略（自动编号）；关键分支节点建议命名 |
| `speaker` | 说话者标签（如 `E`、`JDK`、`P`、`系统`） | 可选 |
| `text` | 台词正文 | **内容数据，不放进 i18n 语言文件** |
| `choices` | 玩家选项 | **最多 4 个**，超出则拆分节点；与 `slider` 互斥 |
| `slider` | 滑杆（数值调节） | `next(value)` 必须返回脚本中存在的 id |
| `next` | 点完继续后的去向 | 目标 id；省略 = 顺序下一个 |
| `effect` | 进入节点时的副作用 | 用于解锁成就等 |

- **跳转规则**：优先按 `id` 找目标 → 找不到则顺序下一个 → 最后一句自动关窗。
- **选项/滑杆互斥**：一个节点只能有 `choices` 或 `slider` 之一。
- **成就/彩蛋**：节点 `effect` 里可调 `unlockAchievement(...)`（参考 `opening.ts`）。

## 四、动手：生成三处改动（每步都向用户汇报）

> AI 内部动作：改 3 个文件。每完成关键一步，用大白话向用户说一句进展。

1. **读现状**：`desktop/src/composables/useStoryDialog.ts`（类型与约束）、
   `desktop/src/story/scripts/opening.ts`（示例）、`desktop/src/composables/useFileSystem.ts`（文件树）。
2. **生成脚本** `desktop/src/story/scripts/<slug>.ts`（导出 `const <Name>Script: StoryNode[]`），
   文件头写 JSDoc（这段剧情是什么、文案来自哪、怎么触发）。
3. **注册**：在 `desktop/src/story/index.ts` 的 `storyScripts` 加一行。
4. **加虚拟文件**：在 `useFileSystem.ts` 用户指定的目录（默认 `home/`）加节点并同步树注释：
   ```ts
   {
     name: '<用户确认的文件名>.exe', type: 'file', content: null,
     storyId: '<与注册表一致的 key>', children: null,
   },
   ```
5. **成就可选**：若用户确认要成就，在 `desktop/src/i18n/locales/*.ts`（5 个语言文件）
   补 `archive.achievementList.<id>.name/description`，并在 `desktop/src/composables/useAchievementUnlocks.ts`
   注册进 `ACHIEVEMENT_BY_ID`。
6. **验证**：`cd desktop && pnpm run type-check` 必须零错误，有错就修到过。
7. **汇报**：告诉用户"剧情文件叫什么、在哪个文件夹、双击就能玩；开发者只要 `pnpm dev` 或提交 git"。

## 五、交付汇报模板（大白话）

> "好了！我把你的剧情做成一个叫 **xxx.exe** 的文件，放在网页桌面的 **home** 文件夹里。开发者启动项目后，你在文件资源管理器里双击它，就能看到你的剧情从头播到尾——包括那几次选择和信任度滑杆。想看效果直接 `pnpm dev` 就行。"

## 六、验收清单（AI 内部逐项检查）

- [ ] `type-check` 零错误
- [ ] 已注册到 `storyScripts`，key 与文件节点 `storyId` 完全一致
- [ ] 虚拟文件节点在用户确认的目录，树注释已同步
- [ ] 所有 `choices` ≤ 4；`slider.next` 返回值都是存在的 id
- [ ] 剧情文本未写入 i18n 语言文件
- [ ] 用户要成就时，5 个语言文件 + 成就注册表已补齐
- [ ] **全程有向用户提问、复述确认，没有擅自决定用户没交代的事**

## 七、常见错误（AI 内部重点检查）

- ❌ 选项超过 4 个 → 拆分或合并，并告知用户。
- ❌ `slider.next` 返回不存在的 id → 检查分支目标节点。
- ❌ 把剧情正文塞进 i18n → 剧情文本是内容数据，只在 `StoryNode` 里。
- ❌ `storyId` 与注册表不一致 → 双击文件无反应。
- ❌ 漏掉 5 个语言文件之一 → `type-check` 报错。
- ❌ 在 `desktop/` 外跑 `pnpm run type-check` → 工作目录必须是 `desktop/`。
- ❌ **文案有 "xxx" 占位/含糊处，AI 自行脑补** → 必须先问用户。
- ❌ **文件命名、目录、分支走向未征求用户意见就定死** → 先问、或用户说"你看着办"后告知决定。
