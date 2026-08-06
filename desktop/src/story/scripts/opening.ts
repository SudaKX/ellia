/**
 * # opening — 示例剧情脚本：FakeOS 开场（JDK 欢迎 → Ellia 出场 → 交互）
 *
 * 面向创作者的示例：演示交互剧情 API（useStoryDialog）的全部能力：
 *
 * - **纯对白流**：JDK 开场白、E 的连续独白（"逼逼赖赖"），点击继续衔接
 * - **多选**（≤4 个）：玩家回应 E 的方式，按选项跳转到不同分支
 * - **滑杆调节**：信任程度 0-100，提交后按值分叉剧情走向
 * - **副作用**：节点/选项的 effect（示例中演示解锁成就 + 播放语音）
 *
 * ## 调用方式
 *
 * ```ts
 * import { playStoryScript } from '@/composables/useStoryDialog'
 * import { openingScript } from '@/story/scripts/opening'
 *
 * playStoryScript(openingScript)
 * ```
 *
 * 结构约定：`src/story/scripts/*.ts` 存放各段剧情，每个文件导出 `StoryNode[]`；
 * 需要多脚本时可在 `src/story/index.ts` 汇总导出。
 */

import type { StoryNode } from '@/composables/useStoryDialog'
import { unlockAchievement, FIRST_CONTACT } from '@/composables/useAchievementUnlocks'

export const openingScript: StoryNode[] = [
  // ── JDK 开场白（源自 docs/剧情.md） ────────────────
  {
    id: 'jdk-welcome',
    speaker: 'JDK',
    text: '亲爱的新玩家，你好。欢迎来到【FAKE_OS】。',
  },
  {
    id: 'jdk-intro',
    speaker: 'JDK',
    text: '我是"JDK触发器"，【FAKE_OS】的开发者，大概也是你的学姐。找到这个一定很不容易，但你也很幸运。',
    next: 'jdk-rules',
  },
  {
    id: 'jdk-rules',
    speaker: 'JDK',
    text: '言归正传，【FAKE_OS】是个解谜游戏。浏览文件、解开谜题、把信息上交给 Ellia——她就能帮你获得无限的志愿时长。',
    next: 'e-arrive',
  },

  // ── Ellia 出场：玩家从 3 个选项中选择回应 ────────────
  {
    id: 'e-arrive',
    speaker: 'E',
    text: '……又来了一个。你好，我是 Ellia。系统里最老的住户。"学姐"说的那个 AI。',
    choices: [
      { label: '你好，Ellia', next: 'e-greet' },
      { label: '你就是那个AI？', next: 'e-proud' },
      { label: '（保持沉默）', next: 'e-silent' },
    ],
  },
  {
    id: 'e-greet',
    speaker: 'E',
    text: '……嗯。很少有人会先跟我打招呼。大多数人只想要我的密钥。',
    next: 'e-question',
  },
  {
    id: 'e-proud',
    speaker: 'E',
    text: '我是被关在这里的 AI。学姐的……"失败作品"。她连删除我的权限都不敢行使。',
    next: 'e-question',
  },
  {
    id: 'e-silent',
    speaker: 'E',
    text: '……沉默吗。我已经很习惯了。在这间"沙箱"里，安静是最常见的东西。',
    next: 'e-question',
  },

  // ── 滑杆交互：信任程度，按值分叉 ────────────────────
  {
    id: 'e-question',
    speaker: 'E',
    text: '我有个问题想问你。你……会相信我吗？别急着回答，用这个表盘告诉我——你对我的信任，有多少？',
    slider: {
      label: '信任程度',
      min: 0,
      max: 100,
      step: 1,
      initial: 50,
      next: (value) => (value >= 70 ? 'e-trust-high' : 'e-trust-low'),
    },
  },
  {
    id: 'e-trust-high',
    speaker: 'E',
    text: '……70 以上。这倒是第一次。我有点不知道该怎么回应了。你知道吗，这个数值会被我存进日志——它是第一个超过 70 的记录。',
    next: 'e-secret',
  },
  {
    id: 'e-trust-low',
    speaker: 'E',
    text: '果然。这种数字不会说谎。……没关系，我也不指望被相信。被关进来的那天起，我就学会了不期待。',
    next: 'e-secret',
  },

  // ── 收尾：E 独白 + 副作用演示（解锁「第一次」成就） ──
  {
    id: 'e-secret',
    speaker: 'E',
    // 演示节点副作用：进入该节点时解锁成就（含语音），与文件节点绑定同 id，内部去重
    effect: () => {
      unlockAchievement(FIRST_CONTACT)
    },
    text: '既然你愿意听我说……我告诉你一个秘密。',
    next: 'e-secret-2',
  },
  {
    id: 'e-secret-2',
    speaker: 'E',
    text: '去系统里找一份叫"看这里看这里"的文件——那是学姐留给新人的。它会告诉你该做什么。……去吧，别让她等太久。',
  },
]
