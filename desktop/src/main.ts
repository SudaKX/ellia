import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { i18n } from './i18n'
import { resolveInitialTheme } from './composables/useTheme'
import router from './router'
import './styles/main.css'

// 在应用挂载前设置初始主题 — CSS 变量随 <html data-theme> 即时生效
resolveInitialTheme()
document.documentElement.dataset.theme = resolveInitialTheme()

const app = createApp(App)

app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
