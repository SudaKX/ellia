<template>
  <div class="app-shell app-shell--terminal">
    <p class="app-shell__line"><span class="app-shell__prompt">&gt;</span> system.init --terminal</p>
    <p class="app-shell__line">Console ready. Awaiting input.</p>
    <p class="app-shell__line app-shell__input">
      <span class="app-shell__prompt">&gt;</span>
      <span class="app-shell__cursor" aria-hidden="true">_</span>
    </p>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 4px;
  padding: 18px;
}

.app-shell--terminal {
  background: var(--canvas);
}

.app-shell__line {
  margin: 0;
  color: var(--text-secondary);
  font: 13px var(--font-mono);
  line-height: 1.5;
}

.app-shell__prompt {
  color: var(--signal-red-soft);
}

.app-shell__input {
  display: flex;
  align-items: center;
  gap: 6px;
}

.app-shell__cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
