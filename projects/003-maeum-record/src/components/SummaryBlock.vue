<script setup lang="ts">
import type { Summary } from '../lib/summary'
import { MOODS } from '../lib/mood'
import MoodChart from './MoodChart.vue'

/** 숫자와 분포만 보여준다. 해석·점수 없음 (screens.md S-04) */
defineProps<{ summary: Summary }>()
</script>

<template>
  <div class="summary stack">
    <p class="days">기록한 날 <strong>{{ summary.recordedDays }}일</strong> / {{ summary.totalDays }}일</p>
    <div class="dist">
      <span v-for="(m, i) in MOODS" :key="m.value" class="dist-item" :title="m.label">
        <span aria-hidden="true">{{ m.emoji }}</span>
        <span class="sr">{{ m.label }}</span>
        {{ summary.distribution[i] }}
      </span>
    </div>
    <MoodChart :daily="summary.daily" />
    <p v-if="summary.topTags.length" class="muted">
      자주 남긴 태그:
      {{ summary.topTags.map((t) => `${t.tag}(${t.count})`).join(', ') }}
    </p>
  </div>
</template>

<style scoped>
.days { margin: 0; }
.dist { display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }
.dist-item { display: inline-flex; align-items: center; gap: 4px; font-size: 1rem; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
