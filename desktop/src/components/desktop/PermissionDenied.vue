<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })
</script>

<template>
  <p class="permission-denied">{{ t('common.permissionDenied') }}</p>
</template>

<style scoped>
.permission-denied {
  margin: 0;
  color: var(--signal-red);
  font: 700 32px var(--font-mono);
}
</style>
