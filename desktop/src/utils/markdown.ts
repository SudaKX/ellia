/**
 * # markdown — Markdown 渲染工具
 *
 * 将 Markdown 文本渲染为安全 HTML，供 `v-html` 使用。
 * 统一走 marked 解析 + DOMPurify 消毒，避免各入口各自实现。
 *
 * - `gfm: true`  ：启用 GitHub 风格（表格 / 任务列表 / 删除线等）
 * - `breaks: true`：单换行渲染为 `<br>`，对中文叙事文本排版友好
 *
 * 注意：任何来自文件的文本在 `v-html` 渲染前都必须经过 DOMPurify 消毒，
 * 防止注入恶意 HTML / 脚本（本工具已内置）。
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/** 将 Markdown 文本渲染为安全 HTML 字符串（可直接用于 v-html） */
export function renderMarkdown(md: string): string {
  const html = marked.parse(md, { async: false }) as string
  return DOMPurify.sanitize(html)
}
