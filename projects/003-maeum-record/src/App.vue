<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import TabBar from './components/TabBar.vue'

const route = useRoute()
const bare = computed(() => route.meta.bare === true)
const showTabs = computed(() => route.meta.tab === true)
const title = computed(() => (route.meta.title as string | undefined) ?? null)
</script>

<template>
  <AppHeader v-if="!bare" :title="title" />
  <main>
    <RouterView />
  </main>
  <TabBar v-if="showTabs" />
</template>
