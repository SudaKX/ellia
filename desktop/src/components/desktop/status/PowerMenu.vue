<template>
  <div class="power-menu">
    <div class="menu-header">
      <span class="menu-title">Power</span>
    </div>
    <div class="menu-body">
      <p class="placeholder-text">Session control placeholder</p>
    </div>
  </div>
</template>

<style scoped>
.power-menu {
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
