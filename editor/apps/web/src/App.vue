<script setup lang="ts">
import { REGISTRY_NAMES } from '@ellia/puzzle-schema'
</script>

<template>
  <h1>Ellia 谜题在线多人编辑器 — M0 骨架</h1>
  <p>pnpm workspace 已接通：apps/web + apps/server + @ellia/puzzle-schema。</p>
  <p>
    覆盖 Mythos 全部 {{ REGISTRY_NAMES.length }} 个注册表：
    {{ REGISTRY_NAMES.join(' / ') }}
  </p>
</template>

<style scoped>
h1 {
  font-weight: 600;
}
</style>
