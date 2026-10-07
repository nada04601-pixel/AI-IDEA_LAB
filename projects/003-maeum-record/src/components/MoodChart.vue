<script setup lang="ts">
import { computed } from 'vue'
import { formatShort } from '../lib/date'
import { moodInfo } from '../lib/mood'

/** 날짜별 흐름. 기록 없는 날은 빈칸(점 없음). */
const props = defineProps<{ daily: { date: string; avg: number | null }[] }>()

const W = 320
const H = 120
const PAD = { l: 16, r: 16, t: 10, b: 22 }

const points = computed(() => {
  const n = props.daily.length
  const step = n > 1 ? (W - PAD.l - PAD.r) / (n - 1) : 0
  return props.daily.map((d, i) => ({
    x: PAD.l + i * step,
    y: d.avg === null ? null : PAD.t + ((5 - d.avg) / 4) * (H - PAD.t - PAD.b),
    ...d,
  }))
})

/** 연속된 기록끼리만 선으로 잇는다 */
const segments = computed(() => {
  const out: string[] = []
  let cur: string[] = []
  for (const p of points.value) {
    if (p.y === null) {
      if (cur.length > 1) out.push(cur.join(' '))
      cur = []
    } else cur.push(`${p.x},${p.y}`)
  }
  if (cur.length > 1) out.push(cur.join(' '))
  return out
})

const labelEvery = computed(() => Math.ceil(props.daily.length / 7))
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" class="chart" role="img" aria-label="날짜별 기분 흐름">
    <line v-for="v in [1, 3, 5]" :key="v" :x1="PAD.l" :x2="W - PAD.r"
      :y1="PAD.t + ((5 - v) / 4) * (H - PAD.t - PAD.b)" :y2="PAD.t + ((5 - v) / 4) * (H - PAD.t - PAD.b)" class="grid" />
    <polyline v-for="(s, i) in segments" :key="i" :points="s" class="line" />
    <template v-for="(p, i) in points" :key="p.date">
      <circle v-if="p.y !== null" :cx="p.x" :cy="p.y" r="4.5" :fill="moodInfo(p.avg!).color" />
      <text v-if="i % labelEvery === 0 || i === points.length - 1" :x="p.x" :y="H - 6" class="tick">{{ formatShort(p.date) }}</text>
    </template>
  </svg>
</template>

<style scoped>
.chart { width: 100%; height: auto; display: block; }
.grid { stroke: var(--line); stroke-width: 1; stroke-dasharray: 2 3; }
.line { fill: none; stroke: var(--text-2); stroke-width: 1.5; opacity: 0.6; }
.tick { font-size: 9px; fill: var(--text-2); text-anchor: middle; }
</style>
