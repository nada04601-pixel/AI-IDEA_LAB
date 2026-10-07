<script setup lang="ts">
import { GUIDES, GUIDE_SECTIONS } from '../content/guides'

/** S-06 첫 진료 가이드 목록 */
</script>

<template>
  <div class="page stack">
    <h1>첫 진료 길잡이</h1>
    <section v-for="s in GUIDE_SECTIONS" :key="s">
      <h2 class="section">{{ s }}</h2>
      <ul class="list card flush">
        <li v-for="g in GUIDES.filter((x) => x.section === s)" :key="g.slug">
          <RouterLink class="list-row" :to="`/guides/${g.slug}`">
            <span>{{ g.title }}</span>
            <span v-if="g.draft" class="badge">준비 중</span>
            <span v-else class="muted" aria-hidden="true">›</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.section { color: var(--text-2); font-size: 0.9rem; margin: 8px 0; }
.flush { padding: 0; }
</style>
