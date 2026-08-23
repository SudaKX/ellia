import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { i18n } from './i18n'
import { resolveInitialTheme } from './composables/useTheme'
import router from './router'
import './styles/main.css'

// 注册多媒体缓存 Service Worker：把图片/音频缓存到用户侧（Cache Storage），
// 缓解低带宽服务器加载慢的问题（见 public/sw.js + src/config/media.ts）。
// 不支持 SW 的环境（如 file:// 直接打开）静默跳过，不影响游戏。
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`)
      .catch(() => undefined)
  })
}

// 在应用挂载前设置初始主题 — CSS 变量随 <html data-theme> 即时生效
resolveInitialTheme()
document.documentElement.dataset.theme = resolveInitialTheme()

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
