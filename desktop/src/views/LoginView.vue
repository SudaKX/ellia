<script setup lang="ts">
/**
 * # 登录页面
 *
 * FakeOS 的登录入口页面。布局模仿桌面主视图：
 * - 顶部状态栏（网络、声音、电源三个菜单）
 * - 居中可拖拽的登录窗口（使用 WindowFrame 组件）
 *
 * ## 窗口管理
 *
 * 登录窗口不经过 WindowService registry（因为这是独立的登录页，
 * 不需要完整的桌面窗口系统）。窗口实例直接 mock 为 WindowInstance 对象。
 *
 * ## 关闭后重开
 *
 * 关闭登录窗口后（`loginWindowVisible = false`），页面中央会出现
 * "打开登录窗口"按钮。这为未来"即时提权验证身份"场景预留了入口——
 * 只需在其他地方调用本页面的 `openLoginWindow` 逻辑即可弹出登录窗。
 */

import { markRaw, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { LogIn, Power, Volume2, Wifi } from 'lucide-vue-next'

import { useAuth } from '@/composables/useAuth'
import { AUTH_ENDPOINTS, USE_REAL_API } from '@/config/api'
import LoginForm from '@/components/desktop/LoginForm.vue'
import WindowFrame from '@/components/desktop/WindowFrame.vue'
import NetworkMenu from '@/components/desktop/status/NetworkMenu.vue'
import PowerMenu from '@/components/desktop/status/PowerMenu.vue'
import SoundMenu from '@/components/desktop/status/SoundMenu.vue'
import StatusMenuButton from '@/components/desktop/status/StatusMenuButton.vue'
import type { WindowInstance } from '@/types/desktop'

const { t } = useI18n({ useScope: 'global' })
const router = useRouter()
const auth = useAuth()

const activeMenuId = ref<string | null>(null)
const loginWindowVisible = ref(true)
const validationMessage = ref('')

/**
 * 进入登录页时向后端校验当前 token 是否仍然有效。
 * 有效 → 保留登录态，用户点击"密钥登录"后进入桌面；
 * 无效 → 清除登录态，显示登录表单。
 */
onMounted(async () => {
  const valid = await auth.validateWithBackend()
  if (valid && auth.isAuthenticated.value) {
    validationMessage.value = t('login.sessionFound')
    return
  }
  // token 无效 → 已由 validateWithBackend 内部调用 logout()
  validationMessage.value = ''
})

function setActiveMenu(menuId: string | null) {
  activeMenuId.value = menuId
}

/** 登录窗口实例（mock，不经过 WindowService registry） */
const loginWindow = ref<WindowInstance>({
  id: 'login-window',
  applicationId: null,
  titleKey: 'login.windowTitle',
  icon: markRaw(LogIn),
  component: markRaw(LoginForm),
  componentProps: {
    onLogin: handleLogin,
    onTokenLogin: handleTokenLogin,
  },
  controls: { minimize: false, close: true },
  mode: 'normal',
  resizable: true,
  filters: {},
  dockable: false,
  x: Math.round((window.innerWidth - 380) / 2),
  y: Math.round((window.innerHeight - 240) / 2),
  width: 380,
  height: 240,
  zIndex: 200,
  isMinimized: false,
  maximizable: true,
  isMaximized: false,
})

/**
 * 密码登录。
 * 切换真实 API：将 `src/config/api.ts` 中 `USE_REAL_API` 改为 `true` 并设置 `API_BASE`。
 */
async function handleLogin(username: string, password: string) {
  if (USE_REAL_API) {
    try {
      const res = await fetch(AUTH_ENDPOINTS.login, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) return
      const data = await res.json()
      auth.login(data.accountType ?? 'player', data.token, data.username ?? username)
      router.push({ name: 'desktop' })
      return
    } catch {
      return
    }
  }

  // Mock 模式
  const mockToken = btoa(`${username}:${Date.now()}`)
  auth.login('player', mockToken, username)
  router.push({ name: 'desktop' })
}

/** 密钥登录：基于已有 token 登录 */
async function handleTokenLogin() {
  if (USE_REAL_API) {
    const savedToken = localStorage.getItem('ell_auth_token')
    if (!savedToken) return
    try {
      const res = await fetch(AUTH_ENDPOINTS.tokenLogin, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: savedToken }),
      })
      if (!res.ok) return
      const data = await res.json()
      auth.login(data.accountType ?? 'player', data.token, data.username)
      router.push({ name: 'desktop' })
      return
    } catch {
      return
    }
  }

  // Mock 模式
  const mockToken = btoa(`token:${Date.now()}`)
  auth.login('player', mockToken)
  router.push({ name: 'desktop' })
}

function openLoginWindow() {
  loginWindowVisible.value = true
}
</script>

<template>
  <div class="login-shell">
    <header class="login-status-bar">
      <div class="login-status-bar__spacer" />
      <div class="login-status-bar__system">
        <StatusMenuButton
          menu-id="network"
          label="Network"
          :icon="Wifi"
          :active-menu-id="activeMenuId"
          @set-active="setActiveMenu"
        >
          <NetworkMenu />
        </StatusMenuButton>
        <StatusMenuButton
          menu-id="sound"
          label="Sound"
          :icon="Volume2"
          :active-menu-id="activeMenuId"
          @set-active="setActiveMenu"
        >
          <SoundMenu />
        </StatusMenuButton>
        <StatusMenuButton
          menu-id="power"
          label="Power"
          :icon="Power"
          :active-menu-id="activeMenuId"
          @set-active="setActiveMenu"
        >
          <PowerMenu />
        </StatusMenuButton>
      </div>
    </header>

    <section class="login-workspace">
      <div class="workspace-grid" aria-hidden="true"></div>
      <p v-if="validationMessage" class="login-validation">{{ validationMessage }}</p>
      <WindowFrame
        v-if="loginWindowVisible"
        :window="loginWindow"
        :is-active="true"
        :filter-ids="{}"
        @close="loginWindowVisible = false"
        @focus="() => {}"
        @minimize="() => {}"
      />
      <button
        v-else
        class="login-reopen"
        type="button"
        @click="openLoginWindow"
      >
        <LogIn :size="16" :stroke-width="1.8" />
        <span>{{ t('login.openButton') }}</span>
      </button>
    </section>
  </div>
</template>

<style scoped>
.login-shell {
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100dvh;
  overflow: hidden;
  background: var(--canvas);
}

.login-status-bar {
  position: relative;
  z-index: 20;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  min-height: 40px;
  padding: 0 18px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-raised);
}

.login-status-bar__spacer {
  /* 占据左侧空间但不显示用户标识 */
}

.login-status-bar__system {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.login-workspace {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 0;
  overflow: hidden;
}

.login-validation {
  position: relative;
  margin: 0;
  padding: 8px 20px;
  border: 1px solid var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-raised);
  font: 600 12px var(--font-ui);
}

.workspace-grid {
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image: linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent, black 14%, black 88%, transparent);
}

.login-reopen {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 24px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  background: var(--surface-raised);
  font: 600 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.login-reopen:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

/* 登录窗口可拖拽缩放，内容溢出时隐藏滚动条（窗口可拉大，不需要滚动） */
.login-workspace :deep(.window-frame__body) {
  scrollbar-width: none;
}

.login-workspace :deep(.window-frame__body)::-webkit-scrollbar {
  width: 0;
  height: 0;
}
</style>
