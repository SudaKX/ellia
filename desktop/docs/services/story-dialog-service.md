# Story Dialog Service

交互剧情系统：为剧情/谜题创作者提供"数据驱动"的对话演出能力。创作者只需写一份 `StoryNode[]` 脚本，其余演出（打字机、玩家选项、滑杆调节、跳转、副作用）全部由服务与播放引擎完成。

## 架构与数据流

```
创作者脚本（src/story/scripts/*.ts → 注册表 src/story/index.ts）
  │  storyId 绑定在文件节点上（FileNode.storyId）
  ▼
触发点（FileExplorer 双击文件 / 任意代码调用 playStoryScript）
  ▼
useStoryDialog.playStoryScript(script)
  │  归一化（补 id、校验选项≤4）→ windowService.create-window（模态）
  ▼
StoryDialog.vue（播放引擎）
  │  打字机对白 → 选项（≤4）/ 滑杆 → 按 id 跳转 → 收尾自动关闭
  ▼
副作用（node/choice/slider 的 effect）：成就解锁、音频播放等
```

- `useStoryDialog`（模块级单例）创建模态窗口；`StoryDialog.vue` 只负责播放。
- DesktopView 持有唯一的 WindowService 实例，setup 时 `initStoryDialog(windowService)` 注册（与成就系统注入 AudioService 同模式）。

## 创作者 API

### playStoryScript

```ts
import { playStoryScript } from '@/composables/useStoryDialog'
import { openingScript } from '@/story/scripts/opening'

playStoryScript(openingScript)
playStoryScript(script, { glitch: true, charDelay: 40 })
```

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `script` | `StoryNode[]` | 剧情节点数组（顺序数组，用 `next`/选项跳转） |
| `options.glitch` | `boolean` | 是否启用 glitch 滤镜（E 不稳定的叙事暗示） |
| `options.charDelay` | `number` | 打字速度（每字符 ms，默认 30） |

### StoryNode

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `string?` | 节点唯一 id（跳转目标）。缺省自动生成 `node-${i}`；给关键分支节点命名 |
| `speaker` | `string?` | 说话者标签（如 `E`、`JDK`、`P`），显示在台词上方 |
| `text` | `string?` | 台词正文（**内容数据，不参与 i18n**，与文件系统内容一致） |
| `choices` | `StoryChoice[]?` | 玩家选项（**1~4 个**，超出忽略并告警）；与 `slider` 互斥 |
| `slider` | `StorySlider?` | 滑杆调节选项；与 `choices` 互斥 |
| `next` | `string?` | 对白读完点击继续后的去向（目标 id）；缺省 = 顺序下一个 |
| `effect` | `() => void?` | 节点进入时执行的副作用（解锁成就、播放音频等） |

### StoryChoice（选项）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `label` | `string` | 选项按钮文案（内容数据） |
| `next` | `string?` | 跳转目标节点 id；缺省 = 顺序下一个 |
| `effect` | `() => void?` | 点击时执行的副作用 |

### StorySlider（滑杆，"滑动变阻器"式）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `label` | `string` | 滑杆标签 |
| `min` / `max` | `number` | 取值区间 |
| `step` | `number?` | 步进，默认 1 |
| `initial` | `number?` | 初始值，默认区间中点 |
| `submitLabel` | `string?` | 提交按钮文案，默认 i18n `story.dialog.submit` |
| `next` | `(value) => string` | 提交后按当前值返回目标节点 id（按值分叉剧情） |
| `effect` | `(value) => void?` | 提交时副作用 |

## 约束

- 选项数量 1 ~ 4（服务层 `MAX_CHOICES` 校验 + 告警，引擎仅渲染前 4 个）。
- `choices` 与 `slider` 互斥；`slider.next` 返回的 id 应存在于脚本中（不存在则顺序下一个）。
- 跳转规则：优先按目标 id 定位 → 缺失则顺序下一个 → 已是最后则自动关闭窗口。
- 剧本文本与按钮文案为**内容数据**（不进 i18n）；引擎 UI 文案（点击继续 / 提交）走 i18n（`story.dialog.*`）。

## 播放引擎状态机（StoryDialog.vue）

```
进入节点（index 变化）
  ├─ node.effect() 触发（成就/音频）
  ├─ 重置打字机（无 text 的纯交互节点直接完成）
  └─ 交互区渲染：
       ├─ choices → 点击 → choice.effect() + 跳转 choice.next
       ├─ slider  → 提交 → slider.effect(v) + 跳转 slider.next(v)
       └─ 无交互   → 点击继续 → 跳转 node.next
越界 → emit('close')，WindowFrame 关闭动画后移除窗口
```

## 触发方式

### 1. 文件绑定（推荐：解谜玩法）

给文件节点加 `storyId`，双击即播放（`src/composables/useFileSystem.ts`）：

```ts
{
  name: 'init.exe', type: 'file', content: null, storyId: 'opening', children: null,
}
```

FileExplorer 双击时按 `storyId` 查注册表播放（通用机制，不写死文件名）。

### 2. 代码调用

任意位置 `import { playStoryScript } from '@/composables/useStoryDialog'` 直接播放（登录后、成就解锁、事件触发均可）。

## 如何新增一段剧情

1. 在 `src/story/scripts/` 新建脚本文件，导出 `StoryNode[]`（参考 `opening.ts`）。
2. 在 `src/story/index.ts` 注册：`'my-story': myStoryScript`。
3. （可选）给目标文件节点设置 `storyId: 'my-story'`，或直接代码调用。

## 与成就 / 音频联动

`StoryNode.effect()` / `StoryChoice.effect()` / `StorySlider.effect(v)` 可复用现有系统：

```ts
import { unlockAchievement, FIRST_CONTACT } from '@/composables/useAchievementUnlocks'

{
  id: 'e-secret', speaker: 'E', text: '我告诉你一个秘密。',
  effect: () => unlockAchievement(FIRST_CONTACT),   // 成就 toast + kei 语音（走音频管线）
}
```

- 成就：`useAchievementUnlocks`（解锁判定去重 + toast + 可选音效，AudioService 由 DesktopView 注入）。
- 音频：解锁音效与所有音频统一走 App.vue 的 AudioService（Web Audio 图，受主音量/静音/频谱控制）。

## 相关文件

| 文件 | 作用 |
| --- | --- |
| `src/composables/useStoryDialog.ts` | 创作者 API 类型 + 服务入口（playStoryScript / initStoryDialog） |
| `src/components/desktop/StoryDialog.vue` | 播放引擎（打字机、选项、滑杆、跳转、副作用） |
| `src/story/index.ts` | 剧情脚本注册表（storyId → 脚本） |
| `src/story/scripts/opening.ts` | 示例脚本（演示全部 API 能力） |
| `src/composables/useAchievementUnlocks.ts` | 成就解锁与音效联动 |
| `src/components/desktop/AchievementToast.vue` | Steam 风格成就弹窗 |
