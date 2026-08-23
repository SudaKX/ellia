/**
 * # mediaPrecache — 多媒体后台预缓存
 *
 * 登录成功后触发，把 `public/` 下的多媒体资源（见 `src/config/media.ts` 清单）
 * 预缓存到用户侧，缓解低带宽服务器加载慢的问题。
 *
 * ## 工作方式
 *
 * 1. **Service Worker 模式（首选）**：向 SW 发送 `PRECACHE` 消息，
 *   由 `public/sw.js` 受限并发（3 个一批）拉取并存入 Cache Storage，
 *    之后所有多媒体请求直接命中本地缓存（cache-first）。
 * 2. **无 SW 回退**：页面侧受限并发 `fetch`，利用浏览器 HTTP 缓存。
 *
 * 全程 fire-and-forget、静默失败：任何异常都不影响登录与游戏。
 */

import { MEDIA_CACHE_URLS } from '@/config/media'

/** 本地标记：已发起过预缓存（避免重复拉取占用带宽） */
const PRECACHED_KEY = 'ellia.media.precached'

/** 无 SW 时的受限并发 fetch 回退（3 个一批，触发浏览器 HTTP 缓存） */
async function precacheViaFetch(urls: string[]): Promise<void> {
  const BATCH = 3
  for (let i = 0; i < urls.length; i += BATCH) {
    await Promise.all(
      urls.slice(i, i + BATCH).map((url) => fetch(url, { mode: 'no-cors' }).catch(() => undefined)),
    )
  }
}

/**
 * 启动多媒体后台预缓存（登录成功后调用，fire-and-forget）。
 *
 * - 已缓存过（本地标记）则跳过，防止每次登录重复拉带宽；
 * - SW 可用 → 消息驱动预缓存；不可用 → fetch 回退；
 * - 全部异常静默，不影响主流程。
 */
export async function startMediaPrecache(): Promise<void> {
  try {
    if (localStorage.getItem(PRECACHED_KEY) === '1') return

    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.ready
      const worker = registration.active
      if (worker) {
        worker.postMessage({ type: 'PRECACHE', urls: MEDIA_CACHE_URLS })
        localStorage.setItem(PRECACHED_KEY, '1')
        return
      }
    }

    // 无 SW 回退：受限并发 fetch 走浏览器 HTTP 缓存
    await precacheViaFetch(MEDIA_CACHE_URLS)
    localStorage.setItem(PRECACHED_KEY, '1')
  } catch {
    // 静默失败：SW 不支持 / 注册未完成等，均不影响游戏
  }
}
