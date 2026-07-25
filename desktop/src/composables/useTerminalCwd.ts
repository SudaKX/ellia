/**
 * # 终端当前工作目录共享状态
 *
 * 供 `cd` / `pwd` / `ls` / `cat` 命令共享同一个 cwd 状态。
 * 模块级单例，所有命令 import 同一个 ref。
 */

import { ref } from 'vue'

/** 当前工作目录路径（以 / 开头，不以 / 结尾，根目录为 '/'） */
const cwd = ref('/home/PLAYER')

/** 规范化路径：合并连续斜杠、去掉尾部斜杠（保留根目录 /） */
function normalizePath(path: string): string {
  if (!path || path === '/') return '/'
  let normalized = path.replace(/\/+/g, '/').replace(/\/$/, '')
  if (!normalized.startsWith('/')) normalized = `/${normalized}`
  return normalized || '/'
}

/** 将相对/绝对路径解析为绝对路径 */
function resolvePath(base: string, target: string): string {
  if (target.startsWith('/')) return normalizePath(target)

  const parts = base === '/' ? [] : base.split('/')
  for (const seg of target.split('/')) {
    if (seg === '.' || seg === '') continue
    if (seg === '..') {
      if (parts.length > 0) parts.pop()
    } else {
      parts.push(seg)
    }
  }
  return parts.length === 0 ? '/' : `/${parts.join('/')}`
}

/**
 * 尝试切换工作目录。返回成功后的路径或 null（路径不存在）。
 */
function changeDirectory(target: string): string | null {
  // 这里需要访问 ls 的文件树，所以先返回目标路径让 cd 命令去校验
  // 简单实现：cd 命令自己校验 / set cwd
  const resolved = resolvePath(cwd.value, target)
  return resolved
}

/** 获取当前 cwd */
function getCwd(): string {
  return cwd.value
}

/** 设置 cwd（由 cd 命令校验后调用） */
function setCwd(path: string): void {
  cwd.value = path
}

export function useTerminalCwd() {
  return { cwd, getCwd, setCwd, resolvePath, changeDirectory }
}
