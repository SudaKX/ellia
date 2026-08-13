/**
 * # story — 剧情脚本注册表
 *
 * 剧情脚本的集中登记处。FileNode.storyId 引用这里的 key：
 * 文件资源管理器双击绑定文件时，按 id 取出脚本播放（见 FileExplorer）。
 *
 * ## 如何新增一段剧情
 *
 * 1. 在 `src/story/scripts/` 新建脚本文件，导出 `StoryNode[]`
 * 2. 在本文件注册：`'my-story': myStoryScript`
 * 3. 给目标文件节点设置 `storyId: 'my-story'`（见 useFileSystem）
 *
 * ## 结构约定
 *
 * - `scripts/*.ts`：具体剧情脚本（内容数据，面向创作者）
 * - `index.ts`：注册表（id → 脚本），统一所有可播放剧情
 */

import type { StoryNode } from '@/composables/useStoryDialog'

import { openingScript } from './scripts/opening'

/** 剧情脚本注册表：storyId → 剧情节点数组 */
export const storyScripts: Record<string, StoryNode[]> = {
  /** 开场剧情：JDK 欢迎 → Ellia 出场 → 玩家选择 → 信任滑杆（home/init.exe 双击触发） */
  opening: openingScript,
}
