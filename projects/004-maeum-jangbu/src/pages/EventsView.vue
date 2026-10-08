<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ledger } from '../lib/store'
import { eventSummary } from '../lib/ledger'
import { ddayLabel, formatDot, formatMD, todayKey } from '../lib/date'
import { formatShort } from '../lib/money'
import { eventTypeIcon } from '../lib/types'

/** S-05 행사 목록 */
const route = useRoute()
const router = useRouter()
const today = todayKey()
const tab = ref<'mine' | 'theirs'>(route.query.tab === 'theirs' ? 'theirs' : 'mine')
const setTab = (t: 'mine' | 'theirs') => {
  tab.value = t
  router.replace({ query: { tab: t } })
}

const byEvent = computed(() => {
  const m = new Map<string, typeof ledger.value.records>()
  for (const r of ledger.value.records) m.set(r.eventId, [...(m.get(r.eventId) ?? []), r])
  return m
})

const mine = computed(() =>
  ledger.value.events
    .filter((e) => e.owner === 'mine')
    .sort((a, b) => b.date.localeCompare(a.date))
    .map((e) => ({ e, s: eventSummary((byEvent.value.get(e.id) ?? []).filter((r) => r.direction === 'received')) })),
)

const theirs = computed(() => {
  const list = ledger.value.events
    .filter((e) => e.owner === 'theirs')
    .map((e) => ({ e, given: (byEvent.value.get(e.id) ?? []).filter((r) => r.direction === 'given') }))
  return {
    upcoming: list.filter((x) => x.e.date >= today).sort((a, b) => a.e.date.localeCompare(b.e.date)),
    past: list.filter((x) => x.e.date < today).sort((a, b) => b.e.date.localeCompare(a.e.date)),
  }
})
const sum = (rs: { amount: number }[]) => rs.reduce((a, r) => a + r.amount, 0)
</script>

<template>
  <div class="page">
    <div class="segment" role="group" aria-label="행사 종류">
      <button :aria-pressed="tab === 'mine'" @click="setTab('mine')">내 행사</button>
      <button :aria-pressed="tab === 'theirs'" @click="setTab('theirs')">상대 행사</button>
    </div>

    <template v-if="tab === 'mine'">
      <div class="stack list-gap">
        <RouterLink v-for="x in mine" :key="x.e.id" :to="`/events/${x.e.id}`" class="card ev">
          <strong>{{ eventTypeIcon(x.e.type) }} {{ x.e.title }}</strong>
          <span class="muted small">{{ formatDot(x.e.date) }}<template v-if="x.e.place"> · {{ x.e.place }}</template></span>
          <span>받음 {{ x.s.count }}건 · <span class="amount received">{{ formatShort(x.s.total) }}</span></span>
          <span v-if="x.s.count" class="muted small">감사 인사 {{ x.s.thanked }}/{{ x.s.count }}</span>
        </RouterLink>
      </div>
      <div v-if="!mine.length" class="card empty"><p class="muted">아직 등록한 내 행사가 없어요.</p></div>
      <RouterLink to="/events/new?owner=mine" class="btn outline add">내 행사 추가</RouterLink>
    </template>

    <template v-else>
      <h2 class="section-title">다가오는 행사</h2>
      <div v-if="theirs.upcoming.length" class="card flush">
        <ul class="list">
          <li v-for="x in theirs.upcoming" :key="x.e.id">
            <RouterLink :to="`/events/${x.e.id}`" class="list-row">
              <span class="grow">{{ formatMD(x.e.date) }} {{ x.e.title }}</span>
              <span v-if="x.given.length" class="given amount small">보냄 {{ formatShort(sum(x.given)) }}</span>
              <span class="badge accent">{{ ddayLabel(x.e.date, today) }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
      <p v-else class="muted none">예정된 행사가 없어요.</p>

      <h2 class="section-title">지난 행사</h2>
      <div v-if="theirs.past.length" class="card flush">
        <ul class="list">
          <li v-for="x in theirs.past" :key="x.e.id">
            <RouterLink :to="`/events/${x.e.id}`" class="list-row">
              <span class="grow">{{ formatMD(x.e.date) }} {{ x.e.title }}<span class="muted small"> · {{ x.e.date.slice(0, 4) }}</span></span>
              <span v-if="x.given.length" class="given amount small">보냄 {{ formatShort(sum(x.given)) }}</span>
              <span v-else class="muted small">{{ x.e.noRecordNeeded ? '기록 안 함' : '보냄 기록 없음' }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
      <p v-else class="muted none">지난 행사가 없어요.</p>
      <RouterLink to="/record?mode=theirs" class="btn outline add">상대 경조사 등록</RouterLink>
    </template>
  </div>
</template>

<style scoped>
.list-gap { margin-top: 14px; }
.ev { display: flex; flex-direction: column; gap: 3px; text-decoration: none; color: var(--text); }
.none { margin: 0 4px; }
.add { margin-top: 16px; }
.empty { margin-top: 14px; }
</style>
