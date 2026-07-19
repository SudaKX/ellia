<template>
  <div class="app-shell">
    <p class="app-shell__label">RECOVERED DATA</p>
    <h2 class="app-shell__title">Archive Viewer</h2>
    <p class="app-shell__hint">No recovered session material available.</p>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
}

.app-shell__label {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.app-shell__title {
  margin: 0;
  color: var(--text-primary);
  font: 600 18px var(--font-ui);
}

.app-shell__hint {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
}
</style>
