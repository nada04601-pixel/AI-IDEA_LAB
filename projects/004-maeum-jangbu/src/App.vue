<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import TabBar from './components/TabBar.vue'
import AddButton from './components/AddButton.vue'
import DialogHost from './components/DialogHost.vue'
import { toastText } from './lib/toast'

const route = useRoute()
const bare = computed(() => route.meta.bare === true)
const showTabs = computed(() => route.meta.tab === true)
const showAdd = computed(() => route.meta.add === true)
const title = computed(() => (route.meta.title as string | undefined) ?? null)
</script>

<template>
  <AppHeader v-if="!bare" :title="title">
    <RouterLink v-if="showTabs" to="/search" class="search" aria-label="검색">🔍</RouterLink>
  </AppHeader>
  <main>
    <RouterView />
  </main>
  <AddButton v-if="showAdd" />
  <TabBar v-if="showTabs" />
  <div v-if="toastText" class="toast" :class="{ low: !showTabs }" role="status">{{ toastText }}</div>
  <DialogHost />
</template>

<style scoped>
.search { display: inline-grid; place-items: center; width: 44px; height: 44px; text-decoration: none; font-size: 1.1rem; }
</style>
