<template>
  <div class="network-menu">
    <div class="menu-header">
      <span class="menu-title">Network</span>
    </div>
    <div class="menu-body">
      <p class="placeholder-text">Connection status placeholder</p>
    </div>
  </div>
</template>

<style scoped>
.network-menu {
  padding: 12px;
}

.menu-header {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-subtle);
}

.menu-title {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.placeholder-text {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
}
</style>
