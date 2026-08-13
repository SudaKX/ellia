/**
 * # 出题器后端接入配置
 *
 * - USE_REMOTE_API = true：登录/题库走后端（server/，见 docs/使用文档.md）
 * - USE_REMOTE_API = false：回退到纯前端 localStorage 模拟（旧行为）
 * - QUESTION_API_BASE：后端地址。
 *   来自 Vite 环境变量 `VITE_QUESTION_API_BASE`：
 *   - 本地开发：.env.development 里配 http://localhost:3000
 *   - 生产构建：不设置 → ''（同源，/api/v1/* 由 Nginx 反代到后端）
 */

export const QUESTION_API_BASE = import.meta.env.VITE_QUESTION_API_BASE ?? ''

/** 是否启用真实后端 API。true = 连接 server/；false = 本地 localStorage 模拟 */
export const USE_REMOTE_API = true
