<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger, eventsById, peopleById } from '../lib/store'
import { formatDot } from '../lib/date'
import { formatShort } from '../lib/money'
import { directionLabel } from '../lib/types'

/** 전체 기록 (홈 → 최근 기록 → 전체 보기) */
const dir = ref<'all' | 'received' | 'given'>('all')
const limit = ref(100)
const rows = computed(() =>
  ledger.value.records
    .filter((r) => dir.value === 'all' || r.direction === dir.value)
    .map((r) => ({ r, p: peopleById.value.get(r.personId), e: eventsById.value.get(r.eventId) }))
    .sort((a, b) => (b.e?.date ?? '').localeCompare(a.e?.date ?? '') || b.r.createdAt - a.r.createdAt),
)
</script>

<template>
  <div class="page no-tab">
    <div class="segment" role="group">
      <button :aria-pressed="dir === 'all'" @click="dir = 'all'">전체</button>
      <button class="received" :aria-pressed="dir === 'received'" @click="dir = 'received'">받음</button>
      <button class="given" :aria-pressed="dir === 'given'" @click="dir = 'given'">보냄</button>
    </div>
    <p class="muted small count">{{ rows.length }}건</p>
    <div v-if="rows.length" class="card flush">
      <ul class="list">
        <li v-for="x in rows.slice(0, limit)" :key="x.r.id">
          <RouterLink :to="`/record?id=${x.r.id}`" class="list-row">
            <span class="grow"><strong>{{ x.p?.name }}</strong><br /><span class="muted small">{{ x.e ? formatDot(x.e.date) : '' }} · {{ x.e?.title }}</span></span>
            <span :class="x.r.direction" class="amount">{{ directionLabel(x.r.direction) }} {{ x.r.amount ? formatShort(x.r.amount) : '' }}</span>
          </RouterLink>
        </li>
      </ul>
    </div>
    <button v-if="rows.length > limit" class="btn outline more" @click="limit += 100">더 보기</button>
  </div>
</template>

<style scoped>
.count { margin: 10px 4px; }
.more { margin-top: 12px; }
</style>
