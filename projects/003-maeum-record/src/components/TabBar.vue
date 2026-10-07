<script setup lang="ts">
const tabs = [
  { to: '/', icon: '✎', label: '기록' },
  { to: '/calendar', icon: '▦', label: '달력' },
  { to: '/visit', icon: '✚', label: '진료 준비' },
  { to: '/guides', icon: '☰', label: '가이드' },
]
</script>

<template>
  <nav class="tabbar" aria-label="주요 메뉴">
    <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="tab" exact-active-class="active">
      <span class="icon" aria-hidden="true">{{ t.icon }}</span>
      <span>{{ t.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.tabbar {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 480px; z-index: 10;
  display: grid; grid-template-columns: repeat(4, 1fr);
  height: calc(var(--tab-h) + env(safe-area-inset-bottom)); padding-bottom: env(safe-area-inset-bottom);
  background: var(--surface); border-top: 1px solid var(--line);
}
.tab {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
  font-size: 0.78rem; color: var(--text-2); text-decoration: none;
}
.icon { font-size: 1.15rem; line-height: 1; }
.active { color: var(--accent); font-weight: 700; }
</style>
