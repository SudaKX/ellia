/**
 * # useRemoteFiles — 远程文件系统服务（真实模式专用）
 *
 * 在 `USE_REAL_API=true` 时，文件资源管理器通过本模块从后端
 * Ellia Mythos API 读取目录树与文件内容，替代前端的静态 mock 树。
 *
 * ## 数据流
 *
 * ```
 * 目录浏览：GET /api/v1/files/d/ls?path=/xxx   → {path, directories, files, tree_version}
 * 读文件内容（两步走）：
 *   1. GET /api/v1/files/{file_id}/{content_token}/content-url → {url, expires_at, content_token}
 *   2. fetch(url) 直接拉对象存储
 * ```
 *
 * 约定：
 * - 面向玩家的浏览使用**动态树**（`/files/d/*`），合并玩家 Artifact；
 * - 预签名 URL **不持久化**（过期即失效，见 expires_at）；
 * - 所有请求由 `apiFetch` 自动附加 Bearer + 解析 RFC 9457 ProblemDetails。
 *
 * ## 错误映射（调用方处理，见 docs/backend-integration.md）
 *
 * | 状态 | 含义 | 前端动作 |
 * |------|------|----------|
 * | 403  | 已知文件但无权限 | 从视图中移除该项 |
 * | 404  | 目录/文件不可见   | 移除本地状态，不区分存在性 |
 * | 412  | content token 过期 | 刷新 tree/version 后仅重试一次 |
 * | 502/503 | 对象存储不可用 | 保留目录状态，提示"暂不可用" |
 *
 * Mock 模式（`USE_REAL_API=false`）不使用本模块，仍走 `useFileSystem` 静态树。
 */

import { FILES_ENDPOINTS } from '@/config/api'
import { apiFetch, ApiError } from '@/utils/http'

/** 后端目录条目（ls 响应中的 directories 项） */
export interface RemoteDirectoryEntry {
  path: string
  display: Record<string, unknown>
}

/** 后端文件摘要（FileSummary） */
export interface RemoteFileSummary {
  file_id: string
  path: string
  version: number
  media_type: string
  size_bytes: number
  content_token: string
  display: Record<string, unknown>
}

/** 后端目录列表响应（`/files/d/ls`） */
export interface RemoteDirectoryListing {
  path: string
  directories: RemoteDirectoryEntry[]
  files: RemoteFileSummary[]
  tree_version: string
}

/** 内容预签名 URL 响应（`/files/{file_id}/{content_token}/content-url`） */
export interface RemoteContentUrl {
  url: string
  expires_at: string
  content_token: string
}

/** 从文件路径提取显示名（如 `/home/notes.txt` → `notes.txt`） */
export function remoteEntryName(path: string): string {
  const segments = path.split('/').filter(Boolean)
  return segments[segments.length - 1] ?? path
}

/**
 * 拉取指定目录的动态列表。
 *
 * @param path 目录绝对路径，默认 `/`
 * @returns 目录列表（directories + files + tree_version）
 * @throws {ApiError} 非 2xx（404 目录不可见、401 token 失效等）
 */
export async function listRemoteDirectory(path = '/'): Promise<RemoteDirectoryListing> {
  const url = `${FILES_ENDPOINTS.dynamicList}?path=${encodeURIComponent(path)}`
  return apiFetch<RemoteDirectoryListing>(url)
}

/**
 * 读取远程文件内容（两步走：content-url → 对象存储）。
 *
 * @param file 后端文件摘要（含 file_id / content_token）
 * @returns 文件文本内容
 * @throws {ApiError} content-url 签发失败（403/404/412/502/503）
 * @throws {Error} 对象存储 URL 拉取失败
 */
export async function fetchRemoteFileContent(file: RemoteFileSummary): Promise<string> {
  const issued = await apiFetch<RemoteContentUrl>(
    FILES_ENDPOINTS.contentUrl(file.file_id, file.content_token),
  )
  const res = await fetch(issued.url)
  if (!res.ok) {
    throw new ApiError({ type: 'about:blank', title: 'Object storage read failed', status: res.status })
  }
  return res.text()
}

/** 判断错误是否为某 HTTP 状态（配合错误映射表使用） */
export function isRemoteStatus(error: unknown, status: number): boolean {
  return error instanceof ApiError && error.status === status
}
