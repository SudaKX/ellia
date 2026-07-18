<template>
  <span class="app-mark" aria-hidden="true">
    <i></i>
    <i></i>
    <i></i>
  </span>
</template>

<style scoped>
.app-mark {
  display: grid;
  grid-template-columns: repeat(3, 4px);
  align-items: end;
  gap: 2px;
  width: 16px;
  height: 16px;
}

.app-mark i {
  display: block;
  background: var(--signal-red);
}

.app-mark i:nth-child(1) {
  height: 6px;
}

.app-mark i:nth-child(2) {
  height: 13px;
}

.app-mark i:nth-child(3) {
  height: 9px;
}
</style>
