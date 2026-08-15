<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import * as adminApi from '../api/admin'
import type { AuthUser, InviteCode } from '../api/types'

const INVITE_TTL_OPTIONS = [
  { label: '1 小时', seconds: 60 * 60 },
  { label: '1 天', seconds: 24 * 60 * 60 },
  { label: '7 天', seconds: 7 * 24 * 60 * 60 },
  { label: '30 天', seconds: 30 * 24 * 60 * 60 },
] as const

const inviteTtlSeconds = ref<number>(INVITE_TTL_OPTIONS[1].seconds)
const invites = ref<InviteCode[]>([])
const users = ref<AuthUser[]>([])
const inviteLoading = ref(false)
const userLoading = ref(false)
const inviteError = ref('')
const userError = ref('')
const notice = ref('')

const statusLabel: Record<InviteCode['status'], string> = {
  unused: '可用',
  used: '已使用',
  expired: '已过期',
}

const userPromoteCandidates = computed(() => users.value.filter((user) => user.role === 'user'))

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

async function loadInvites(): Promise<void> {
  inviteLoading.value = true
  inviteError.value = ''
  try {
    const response = await adminApi.listInvites()
    invites.value = response.invites
  } catch (error) {
    inviteError.value = error instanceof Error ? error.message : '邀请码列表加载失败'
  } finally {
    inviteLoading.value = false
  }
}

async function loadUsers(): Promise<void> {
  userLoading.value = true
  userError.value = ''
  try {
    const response = await adminApi.listUsers()
    users.value = response.users
  } catch (error) {
    userError.value = error instanceof Error ? error.message : '用户列表加载失败'
  } finally {
    userLoading.value = false
  }
}

async function onGenerateInvite(): Promise<void> {
  inviteError.value = ''
  notice.value = ''
  inviteLoading.value = true
  try {
    await adminApi.createInvite(inviteTtlSeconds.value)
    notice.value = '邀请码已生成'
    await loadInvites()
  } catch (error) {
    inviteError.value = error instanceof Error ? error.message : '邀请码生成失败'
  } finally {
    inviteLoading.value = false
  }
}

async function onCopyInvite(code: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(code)
    notice.value = `已复制邀请码 ${code}`
  } catch {
    window.prompt('当前环境无法自动复制，请手动复制邀请码：', code)
  }
}

async function onRevokeInvite(code: string): Promise<void> {
  if (!window.confirm(`确定作废邀请码 ${code} 吗？作废后无法用于注册。`)) return
  inviteError.value = ''
  try {
    await adminApi.revokeInvite(code)
    notice.value = '邀请码已作废'
    await loadInvites()
  } catch (error) {
    inviteError.value = error instanceof Error ? error.message : '邀请码作废失败'
  }
}

async function onPromoteUser(user: AuthUser): Promise<void> {
  if (!window.confirm(`确定将用户 ${user.username} 提权为 admin 吗？`)) return
  userError.value = ''
  try {
    await adminApi.promoteUser(user.id)
    notice.value = `用户 ${user.username} 已提权为 admin`
    await loadUsers()
  } catch (error) {
    userError.value = error instanceof Error ? error.message : '用户提权失败'
  }
}

onMounted(() => {
  void Promise.all([loadInvites(), loadUsers()])
})
</script>

<template>
  <main class="page">
    <header class="card card--fill">
      <h1>管理面板</h1>
      <p class="muted">邀请码与用户角色管理（仅 admin 可见）</p>
    </header>

    <p v-if="notice" class="alert alert--success" role="status">{{ notice }}</p>

    <div class="grid--2">
      <section class="card" aria-labelledby="invites-title">
        <div class="card__header">
          <h2 id="invites-title">邀请码</h2>
          <span class="muted">{{ invites.length }} 条</span>
        </div>

        <form class="field" @submit.prevent="onGenerateInvite">
          <label for="invite-ttl">有效期</label>
          <div class="row">
            <select id="invite-ttl" v-model.number="inviteTtlSeconds" :disabled="inviteLoading">
              <option v-for="option in INVITE_TTL_OPTIONS" :key="option.seconds" :value="option.seconds">
                {{ option.label }}
              </option>
            </select>
            <button class="btn btn--primary" type="submit" :disabled="inviteLoading">
              {{ inviteLoading ? '生成中…' : '生成邀请码' }}
            </button>
          </div>
        </form>

        <p v-if="inviteError" class="alert alert--error" role="alert">{{ inviteError }}</p>
        <p v-if="inviteLoading && invites.length === 0" class="loading">正在加载邀请码…</p>

        <table v-if="invites.length > 0" class="data-table">
          <thead>
            <tr>
              <th scope="col">邀请码</th>
              <th scope="col">过期时间</th>
              <th scope="col">状态</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="invite in invites" :key="invite.code">
              <td><code class="mono">{{ invite.code }}</code></td>
              <td>{{ formatDateTime(invite.expires_at) }}</td>
              <td><span class="badge" :class="`badge--${invite.status}`">{{ statusLabel[invite.status] }}</span></td>
              <td>
                <div class="row">
                  <button
                    v-if="invite.status === 'unused'"
                    class="btn btn--text btn--small"
                    type="button"
                    @click="onCopyInvite(invite.code)"
                  >
                    复制
                  </button>
                  <button
                    v-if="invite.status === 'unused'"
                    class="btn btn--danger btn--small"
                    type="button"
                    @click="onRevokeInvite(invite.code)"
                  >
                    作废
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!inviteLoading" class="muted">还没有邀请码。</p>
      </section>

      <section class="card" aria-labelledby="users-title">
        <div class="card__header">
          <h2 id="users-title">用户</h2>
          <span class="muted">{{ users.length }} 个用户</span>
        </div>

        <p v-if="userError" class="alert alert--error" role="alert">{{ userError }}</p>
        <p v-if="userLoading && users.length === 0" class="loading">正在加载用户…</p>

        <table v-if="users.length > 0" class="data-table">
          <thead>
            <tr>
              <th scope="col">用户名</th>
              <th scope="col">角色</th>
              <th scope="col">创建时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.username }}</td>
              <td><span class="badge" :class="`badge--${user.role}`">{{ user.role }}</span></td>
              <td>{{ formatDateTime(user.created_at) }}</td>
              <td>
                <button
                  v-if="user.role === 'user'"
                  class="btn btn--tonal btn--small"
                  type="button"
                  @click="onPromoteUser(user)"
                >
                  提权为 admin
                </button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="!userLoading" class="muted">还没有用户。</p>

        <p v-if="userPromoteCandidates.length > 0" class="hint">
          还有 {{ userPromoteCandidates.length }} 个 user 账号可以提权。
        </p>
      </section>
    </div>
  </main>
</template>
