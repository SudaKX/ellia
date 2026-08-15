import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const theme = useThemeStore(pinia)
theme.initialize()

// 在挂载前恢复会话，避免路由守卫出现登录页闪烁。
const auth = useAuthStore(pinia)
await auth.initialize()

app.use(router)
app.mount('#app')
