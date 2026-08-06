/**
 * # usePlayerFiles — 玩家本地覆盖层（持久化存档）
 *
 * 玩家对 `home/PLAYER/` 内文件的修改，写入**浏览器本地**（localStorage），
 * 与静态基线文件树（useFileSystem 的 rootTree）叠加：
 *
 * ```
 * 读文件 = 本地覆盖层（玩家改过的版本，localStorage） ?? 静态基线（系统下发版本）
 * 写文件 = 仅 home/PLAYER/ 允许 → 写覆盖层 + localStorage
 *          其他目录 → 保持"权限不足"叙事（不落盘）
 * ```
 *
 * ## 为什么用 localStorage 而非 IndexedDB
 *
 * 当前场景是"少量文本文件"（笔记/档案/玩家产出），localStorage 足够且与项目
 * 现有做法一致（音量、成就解锁均已用 localStorage）。若未来需要大文件/结构化
 * 数据，把本模块内部换成 IndexedDB 即可，调用方无需改动。
 *
 * ## 纯前端的边界
 *
 * 数据只存在于玩家浏览器（换设备/清缓存会丢失）。跨设备同步需后端 checkpoint
 * 接口（见 docs/backend-integration.md），接入时把 `loadPlayerFile`/`savePlayerFile`
 * 替换为远程读写即可。
 *
 * ## @example
 *
 * ```ts
 * import { isPlayerWritable, savePlayerFile, loadPlayerFile } from '@/composables/usePlayerFiles'
 *
 * savePlayerFile('/home/PLAYER/note.txt', '新内容')   // true（允许）
 * savePlayerFile('/etc/shadow', 'hack')              // false（拒绝）
 * loadPlayerFile('/home/PLAYER/note.txt')            // '新内容' | null
 * ```
 */

/** localStorage key 前缀：路径规范化后拼在其后（如 .../home/PLAYER/note.txt） */
const STORAGE_PREFIX = 'ellia:player-file:'

/** 玩家可写目录（绝对路径前缀，含尾部斜杠） */
const PLAYER_DIR_PREFIX = '/home/PLAYER/'

/**
 * 判断路径是否在玩家可写目录内。
 * 仅 `home/PLAYER/` 下的**文件**允许写入，系统目录一律拒绝。
 *
 * @param path - 绝对路径（如 '/home/PLAYER/note.txt'）
 * @returns true 表示允许玩家写入
 */
export function isPlayerWritable(path: string): boolean {
  return path.startsWith(PLAYER_DIR_PREFIX) && !path.endsWith('/')
}

/** 把绝对路径转成稳定的 localStorage key */
function storageKey(path: string): string {
  return STORAGE_PREFIX + path
}

/**
 * 保存玩家文件内容到本地覆盖层。
 *
 * @param path    - 绝对路径
 * @param content - 文件内容
 * @returns true 表示已写入本地；路径不可写或存储失败返回 false
 */
export function savePlayerFile(path: string, content: string): boolean {
  if (!isPlayerWritable(path)) return false
  try {
    localStorage.setItem(storageKey(path), content)
    return true
  } catch {
    return false
  }
}

/**
 * 读取玩家本地覆盖层内容（仅返回玩家**改过**的版本）。
 *
 * @param path - 绝对路径
 * @returns 本地版本内容；玩家未改过该文件（或读取失败）返回 null
 */
export function loadPlayerFile(path: string): string | null {
  try {
    return localStorage.getItem(storageKey(path))
  } catch {
    return null
  }
}

/**
 * 清除玩家本地覆盖层（"重置存档"）。
 * 之后所有文件回到静态基线下发的原始版本。
 */
export function resetPlayerFiles(): void {
  try {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i)
      if (key?.startsWith(STORAGE_PREFIX)) keys.push(key)
    }
    keys.forEach((key) => localStorage.removeItem(key))
  } catch {
    /* ignore */
  }
}
