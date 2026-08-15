<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<template>
  <main class="page">
    <header class="card card--fill">
      <h1>项目</h1>
      <p>
        你好，<strong>{{ auth.user?.username }}</strong>（{{ auth.user?.role }}）。
      </p>
      <p class="muted">项目列表将在 M1.2 落地；当前登录态与权限体系已经可用。</p>
    </header>

    <section class="card" aria-labelledby="capability-title">
      <h2 id="capability-title">当前可用能力</h2>
      <div class="stack">
        <p>· 登录 / 登出 / 会话恢复</p>
        <p>· 一次性邀请码注册</p>
        <p v-if="auth.isAdmin">· 管理面板：邀请码管理与用户提权</p>
        <p v-else>· 以 user 角色登录；管理功能需要 admin 权限</p>
      </div>
      <div class="divider"></div>
      <div class="row">
        <RouterLink v-if="auth.isAdmin" class="btn btn--tonal" to="/admin">前往管理面板</RouterLink>
      </div>
    </section>
  </main>
</template>
