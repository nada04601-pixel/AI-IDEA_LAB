<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{ title: string | null }>()
const router = useRouter()

function back() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
</script>

<template>
  <header class="header">
    <template v-if="title">
      <button class="icon-btn" aria-label="뒤로" @click="back">←</button>
      <span class="title">{{ title }}</span>
    </template>
    <span v-else class="brand">마음기록</span>
    <span class="spacer" />
    <RouterLink v-if="$route.name !== 'help'" to="/help" class="help-link">도움받을 곳</RouterLink>
    <RouterLink v-if="$route.name !== 'settings'" to="/settings" class="icon-btn" aria-label="설정">⚙</RouterLink>
  </header>
</template>

<style scoped>
.header {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 8px;
  padding: calc(10px + env(safe-area-inset-top)) 12px 10px 16px;
  background: var(--bg); border-bottom: 1px solid var(--line);
}
.brand { font-weight: 700; font-size: 1.05rem; }
.title { font-weight: 600; }
.spacer { flex: 1; }
.help-link {
  font-size: 0.9rem; font-weight: 600; color: var(--help); text-decoration: none;
  padding: 6px 12px; border-radius: 999px; border: 1px solid var(--help);
}
.icon-btn {
  display: inline-grid; place-items: center; width: 40px; height: 40px; border: 0; background: none;
  font-size: 1.2rem; text-decoration: none; color: var(--text); border-radius: 10px;
}
@media print { .header { display: none; } }
</style>
