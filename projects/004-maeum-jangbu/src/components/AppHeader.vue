<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{ title: string | null }>()
const router = useRouter()

function back() {
  if (window.history.state?.back) router.back()
  else router.push('/')
}
</script>

<template>
  <header class="header">
    <template v-if="title">
      <button class="icon-btn" aria-label="뒤로" @click="back">←</button>
      <span class="title">{{ title }}</span>
    </template>
    <span v-else class="brand">마음장부</span>
    <span class="spacer" />
    <slot />
  </header>
</template>

<style scoped>
.header {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 6px; min-height: 56px;
  padding: calc(8px + env(safe-area-inset-top)) 8px 8px 16px;
  background: var(--bg); border-bottom: 1px solid var(--line);
}
.header:has(.icon-btn:first-child) { padding-left: 4px; }
.brand { font-weight: 800; font-size: 1.1rem; color: var(--accent); }
.title { font-weight: 700; font-size: 1.02rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spacer { flex: 1; }
.icon-btn {
  display: inline-grid; place-items: center; width: 44px; height: 44px; border: 0; background: none;
  font-size: 1.25rem; text-decoration: none; color: var(--text); border-radius: 10px;
}
@media print { .header { display: none; } }
</style>
