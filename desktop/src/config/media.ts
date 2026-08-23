/**
 * # 多媒体资源缓存清单
 *
 * 列出 `public/` 下所有多媒体资源（图片/音频），供登录后后台预缓存到用户侧
 * （Service Worker Cache Storage / 浏览器 HTTP 缓存），缓解低带宽服务器加载慢的问题。
 *
 * ## 使用说明
 *
 * - 新增图片/音频到 `public/` 后，**必须同步在此清单追加对应路径**，否则不会被预缓存。
 * - 路径基于 `import.meta.env.BASE_URL`（如 `/console/`），与页面/资源同源。
 * - 缓存行为由 `public/sw.js`（Service Worker，cache-first）+ `src/utils/mediaPrecache.ts` 驱动。
 */

const base = import.meta.env.BASE_URL

/** 图片资源（相对 base） */
const IMAGES = [
  // ellia 表情（AI 窗口 halftone 头像）
  'images/ellia_little/ellia_normal.png',
  'images/ellia_little/ellia_normal_speak.png',
  'images/ellia_little/ellia_happy.png',
  'images/ellia_little/ellia_happy_speak.png',
  'images/ellia_little/ellia_shy.png',
  'images/ellia_little/ellia_cattiness.png',
  'images/ellia_little/ellia_cattiness_speak.png',
  'images/ellia_little/ellia_dishappy.png',
  'images/ellia_little/ellia_angry.png',
  'images/ellia_little/ellia_confuse.png',
  // ellia 立绘（形象工程剧情 / 图片浏览）
  'images/ellia_big/ellia_1.png',
  'images/ellia_big/ellia_2.png',
  'images/ellia_big/ellia_3.png',
  'images/ellia_big/ellia_4.png',
  // 其他角色立绘（kei 表情 / 全身体 / rio / Chiaki）
  'images/kei/kei_normal1.webp',
  'images/kei/kei_smile1.webp',
  'images/kei/kei_speak1.webp',
  'images/kei/kei_happy2.webp',
  'images/kei/kei_happy3.webp',
  'images/kei/kei_happy_to_tear.webp',
  'images/kei/kei_shock1.webp',
  'images/kei/kei_shock2.webp',
  'images/kei/kei_awkward.webp',
  'images/kei/kei_awkward2.webp',
  'images/kei/kei_veryawkward.webp',
  'images/kei/kei_annoy1.webp',
  'images/kei/kei_小悲.webp',
  'images/kei/kei_大悲.webp',
  'images/kei/kei_超大悲_tear.webp',
  'images/kei/kei_小急.webp',
  'images/kei/kei_大急.webp',
  'images/kei/kei_睁眼小急.webp',
  'images/kei/kei_睁眼大急.webp',
  'images/kei/kei_急眼的不得了.webp',
  'images/kei/kei_毁灭模式启动.webp',
  'images/kei/kei_让我看看!(脸红).webp',
  'images/kei/kei_哟,你脸红了.webp',
  'images/kei_full_body/kei_正常立绘.png',
  'images/kei_full_body/kei_amas立绘.png',
  'images/kei_full_body/kei_十字神明立绘.png',
  'images/rio/rio.png',
  'images/rio/rio_冬装.png',
  'images/Chiaki/千明立绘.png',
  'images/Chiaki/千明_泳装立绘.png',
  'images/Chiaki/千明同人.jpg',
  'images/小春马赛克.webp',
  'images/ai-assistant-a.png',
  'images/ai-assistant-b.png',
]

/** 音频资源（相对 base） */
const AUDIOS = [
  'sounds/kei/kei_老师请求的话……也没办法了呢.ogg',
  'sounds/kei/kei_给我等着瞧.ogg',
  'sounds/kei/kei_竟敢.ogg',
  'sounds/kei/kei_真是无聊呢.ogg',
  'sounds/kei/kei_eventmission_2_1.ogg',
  'sounds/kei/kei_eventmission_2_2.ogg',
  'sounds/kei/kei_eventmission_2_3.ogg',
  'sounds/koyuki/koyuki.ogg',
  'sounds/shihuai/关羽之歌.mp3',
]

/** 全部预缓存多媒体 URL（已拼接 base） */
export const MEDIA_CACHE_URLS: string[] = [...IMAGES, ...AUDIOS].map((p) => `${base}${p}`)
