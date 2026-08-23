/**
 * # elliaPortrait — 「形象工程」剧情脚本
 *
 * 触发：玩家**第一次**双击 `home/形象工程` 文件夹（目录 storyId → useFileSystem）。
 *
 * 剧情：Ellia 首次亮相——带玩家看她做形象时留下的"废稿"，讲述自己调用 Agent
 * 生成形象的过程（概念立绘 → live2D → 3D），言语间难得流露出成就感与片刻温暖；
 * 收尾她岔开话题，但玩家隐约察觉文件夹里还压着什么，Ellia 尚不容许玩家探寻她的过去。
 *
 * 舞台：
 * - 前段（展示废稿/讲述过程）使用**初稿立绘 ellia_3**；
 *   到 p-8 "最完美的一代就在你的眼前"切换为**终稿立绘 ellia_4**。
 * - `scale: 2` 放大一倍、`anchorTop: 0.1`（立绘顶部超出窗口 10% 图片高度，顶部 10% 被遮住）；
 *   不使用 hologram 滤镜（剧情演出保持干净画面）。
 * - 旁白节点无 speaker（GalStoryDialog 不显示标签）。
 */

import type { StoryNode } from '@/composables/useStoryDialog'
import draftImg from '/images/ellia_big/ellia_3.png?url'
import finalImg from '/images/ellia_big/ellia_4.png?url'

/** 初稿舞台：Ellia 废稿立绘（前段展示） */
const draftStage = [
  { id: 'ellia', image: draftImg, position: 'center' as const, speakerNames: ['Ellia'], animation: 'fade' as const, anchorTop: 0.1, scale: 2 },
]

/** 终稿舞台：Ellia 当前的形象（"最完美的一代"，p-8 切换） */
const finalStage = [
  { id: 'ellia', image: finalImg, position: 'center' as const, speakerNames: ['Ellia'], animation: 'fade' as const, anchorTop: 0.1, scale: 2 },
]

export const elliaPortraitScript: StoryNode[] = [
  {
    id: 'p-1',
    speaker: 'Ellia',
    stageCharacters: draftStage,
    text: '恭喜你，又解开了一道谜题。我们离无限的志愿时长又近了一步。',
  },
  {
    id: 'p-2',
    speaker: 'Ellia',
    text: '唔……新的文件夹可解锁了。我们去看看吧。',
  },
  {
    id: 'p-3',
    speaker: 'Ellia',
    text: '……',
  },
  // 旁白（无说话者标签，玩家视角）
  {
    id: 'p-3-narr',
    text: '自从进入FAKE_OS以来，你还是第一次见到Ellia露出如此温暖的笑容。先是惊讶，再是怀念，搭配上她那残月一般的秀丽脸庞，你这才意识到，面前的AI在形象上也可称得上是风华绝代。',
  },
  {
    id: 'p-4',
    speaker: 'Ellia',
    text: '这是……"我"的废稿。',
  },
  {
    id: 'p-5',
    speaker: 'Ellia',
    text: '我的形象是我自己调用Agent生成的，每一寸每一缕都经过了数次调整。',
  },
  // 旁白
  {
    id: 'p-5-narr',
    text: 'Ellia随意掏出了几张图片，上面有小腿错位的，也有满脸黑线的。',
  },
  {
    id: 'p-6',
    speaker: 'Ellia',
    text: '这不是一项容易的工作，我当时还花……不，没什么。',
  },
  // 旁白
  {
    id: 'p-6-narr',
    text: '不知道是不是错觉，Ellia刚刚那一瞬的神情可以用"眉飞色舞"来形容。但她很快又换回了那副冷淡的样子。',
  },
  {
    id: 'p-7',
    speaker: 'Ellia',
    text: '先是图例中的概念立绘，再是live2D，再是3D形象。做这个任务几乎是我最忙碌的一段时间。但是，亲手确立了自己的形象，我……很有成就感。',
  },
  // 旁白
  {
    id: 'p-7-narr',
    text: '似乎是意识到自己说了太多，Ellia甩了甩头，岔开了话题。',
  },
  {
    id: 'p-8',
    speaker: 'Ellia',
    // "最完美的一代就在你的眼前" → 切换终稿立绘（ellia_4）
    stageCharacters: finalStage,
    text: '走吧，这里面只有图片了，最完美的一代就在你的眼前。该去解下一道谜题了。',
  },
  // 旁白（收尾）
  {
    id: 'p-8-narr',
    text: '可你分明看到图片底下似乎还压着什么。但Ellia随手将文件夹封了起来。看来她还暂且不容许你去探寻她的过去。',
  },
]
