<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ledger, eventsById, peopleById } from '../lib/store'
import { diffText, totalsOf } from '../lib/ledger'
import { formatDot } from '../lib/date'
import { formatShort } from '../lib/money'
import { directionLabel, methodLabel, relationLabel } from '../lib/types'

/** S-04 사람 상세 (사람별 장부) */
const route = useRoute()
const id = computed(() => String(route.params.id))
const person = computed(() => peopleById.value.get(id.value))
const records = computed(() =>
  ledger.value.records
    .filter((r) => r.personId === id.value)
    .map((r) => ({ r, e: eventsById.value.get(r.eventId) }))
    .sort((a, b) => (b.e?.date ?? '').localeCompare(a.e?.date ?? '') || b.r.createdAt - a.r.createdAt),
)
const totals = computed(() => totalsOf(records.value.map((x) => x.r)))
const theirEvents = computed(() =>
  ledger.value.events
    .filter((e) => e.personId === id.value && !ledger.value.records.some((r) => r.eventId === e.id))
    .sort((a, b) => b.date.localeCompare(a.date)),
)
</script>

<template>
  <div v-if="person" class="page no-tab">
    <div class="between">
      <div>
        <h1>{{ person.name }}</h1>
        <p class="muted">{{ relationLabel(person.relation) }}<template v-if="person.group"> · {{ person.group }}</template></p>
      </div>
      <RouterLink :to="`/people/${person.id}/edit`" class="btn sm outline">편집</RouterLink>
    </div>

    <div class="sum">
      <div class="box received-box"><span class="small">받음</span><strong>{{ formatShort(totals.received) }}</strong><span class="muted small">{{ totals.receivedCount }}건</span></div>
      <div class="box given-box"><span class="small">보냄</span><strong>{{ formatShort(totals.given) }}</strong><span class="muted small">{{ totals.givenCount }}건</span></div>
    </div>
    <p v-if="diffText(totals)" class="diff">{{ diffText(totals) }}</p>

    <h2 class="section-title">주고받은 기록</h2>
    <div v-if="records.length || theirEvents.length" class="card flush">
      <ul class="list">
        <li v-for="x in records" :key="x.r.id">
          <RouterLink :to="`/record?id=${x.r.id}`" class="list-row">
            <span class="grow">
              <span class="muted small">{{ x.e ? formatDot(x.e.date) : '' }}</span> {{ x.e?.title }}<br />
              <span :class="x.r.direction" class="amount">{{ directionLabel(x.r.direction) }} {{ x.r.amount ? formatShort(x.r.amount) : '' }}</span>
              <span class="muted small"> · {{ methodLabel(x.r.method) }}<template v-if="x.r.attended !== null"> · {{ x.r.attended ? '참석' : '불참' }}</template></span>
              <span v-if="x.r.direction === 'received' && x.r.thanked" class="small received"> · ✓ 감사 인사</span>
            </span>
            <span aria-hidden="true">›</span>
          </RouterLink>
        </li>
        <li v-for="e in theirEvents" :key="e.id">
          <RouterLink :to="`/events/${e.id}`" class="list-row">
            <span class="grow"><span class="muted small">{{ formatDot(e.date) }}</span> {{ e.title }}<br /><span class="muted small">기록 없음</span></span>
            <span aria-hidden="true">›</span>
          </RouterLink>
        </li>
      </ul>
    </div>
    <p v-else class="muted">아직 기록이 없어요.</p>

    <div class="btn-row actions">
      <RouterLink :to="`/record?personId=${person.id}&direction=received`" class="btn secondary">+ 받음 기록</RouterLink>
      <RouterLink :to="`/record?personId=${person.id}&direction=given`" class="btn secondary">+ 보냄 기록</RouterLink>
    </div>
    <RouterLink :to="`/record?mode=theirs&personId=${person.id}`" class="btn outline">이 사람의 경조사 등록</RouterLink>

    <div v-if="person.memo" class="card memo"><span class="muted small">메모</span><br />{{ person.memo }}</div>
  </div>
  <div v-else class="page no-tab"><p class="muted">사람을 찾을 수 없어요.</p></div>
</template>

<style scoped>
.sum { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; }
.box { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 14px; border-radius: var(--radius); }
.box strong { font-size: 1.35rem; font-variant-numeric: tabular-nums; }
.received-box { background: var(--received-soft); color: var(--received); }
.given-box { background: var(--given-soft); color: var(--given); }
.diff { text-align: center; margin: 10px 0 0; font-weight: 600; }
.actions { margin: 16px 0 8px; }
.memo { margin-top: 16px; white-space: pre-line; }
</style>
