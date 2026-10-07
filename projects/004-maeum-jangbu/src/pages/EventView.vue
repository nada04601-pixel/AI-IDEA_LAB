<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ledger, eventsById, peopleById } from '../lib/store'
import { eventSummary, receivedFrom } from '../lib/ledger'
import { ddayLabel, formatDot, todayKey } from '../lib/date'
import { formatShort, formatSentence } from '../lib/money'
import { updateEvent, updateRecord } from '../lib/db'
import { METHODS, directionLabel, eventTypeIcon, methodLabel, relationLabel } from '../lib/types'
import { showToast } from '../lib/toast'

/** S-06 행사 상세 */
const route = useRoute()
const today = todayKey()
const id = computed(() => String(route.params.id))
const event = computed(() => eventsById.value.get(id.value))
const owner = computed(() => (event.value?.personId ? peopleById.value.get(event.value.personId) : undefined))

const q = ref('')
const onlyUnthanked = ref(false)
const sort = ref<'name' | 'amount' | 'recent'>('recent')

const records = computed(() => ledger.value.records.filter((r) => r.eventId === id.value))
const received = computed(() => records.value.filter((r) => r.direction === 'received'))
const summary = computed(() => eventSummary(received.value))
const methodText = computed(() =>
  METHODS.filter((m) => summary.value.byMethod[m.value]).map((m) => `${m.label} ${summary.value.byMethod[m.value]}`).join(' · '),
)

const rows = computed(() => {
  const s = q.value.trim()
  const list = received.value
    .map((r) => ({ r, p: peopleById.value.get(r.personId) }))
    .filter((x) => !s || x.p?.name.includes(s) || x.p?.group.includes(s))
    .filter((x) => !onlyUnthanked.value || !x.r.thanked)
  if (sort.value === 'name') list.sort((a, b) => (a.p?.name ?? '').localeCompare(b.p?.name ?? '', 'ko'))
  else if (sort.value === 'amount') list.sort((a, b) => b.r.amount - a.r.amount)
  else list.sort((a, b) => b.r.createdAt - a.r.createdAt)
  return list
})

// 상대 행사
const given = computed(() => records.value.filter((r) => r.direction === 'given'))
const reference = computed(() => (owner.value ? receivedFrom(owner.value.id, ledger.value.records, ledger.value.events) : []))

async function toggleThanked(id: string, v: boolean) {
  await updateRecord(id, { thanked: v })
}

async function toggleNoRecord() {
  if (!event.value) return
  const v = !event.value.noRecordNeeded
  await updateEvent(event.value.id, { noRecordNeeded: v })
  showToast(v ? '홈의 "기록이 비어 있는 경조사"에서 뺐어요' : '다시 홈에 보여 드릴게요', 2600)
}
</script>

<template>
  <div v-if="event" class="page no-tab">
    <div class="between">
      <div class="grow">
        <h1>{{ eventTypeIcon(event.type) }} {{ event.title }}</h1>
        <p class="muted">{{ formatDot(event.date) }}<template v-if="event.place"> · {{ event.place }}</template></p>
      </div>
      <RouterLink :to="`/events/${event.id}/edit`" class="btn sm outline">편집</RouterLink>
    </div>

    <!-- 내 행사 -->
    <template v-if="event.owner === 'mine'">
      <div class="card summary">
        <p class="big">받음 {{ summary.count }}건 · <span class="received">{{ formatShort(summary.total) }}</span></p>
        <p v-if="methodText" class="muted small">{{ methodText }}</p>
        <p v-if="summary.count" class="muted small">감사 인사 {{ summary.thanked }} / {{ summary.count }}</p>
      </div>

      <div class="tools">
        <input v-model="q" class="field" type="search" placeholder="이름 검색" aria-label="이름 검색" />
        <div class="between">
          <label class="row small"><input v-model="onlyUnthanked" type="checkbox" /> 감사 인사 안 한 사람만</label>
          <select v-model="sort" class="sort" aria-label="정렬">
            <option value="recent">입력순</option>
            <option value="name">이름순</option>
            <option value="amount">금액순</option>
          </select>
        </div>
      </div>

      <div v-if="rows.length" class="card flush">
        <ul class="list">
          <li v-for="x in rows" :key="x.r.id" class="row item">
            <input
              type="checkbox"
              class="check"
              :checked="x.r.thanked"
              :aria-label="`${x.p?.name} 감사 인사 완료`"
              @change="toggleThanked(x.r.id, ($event.target as HTMLInputElement).checked)"
            />
            <RouterLink :to="`/record?id=${x.r.id}`" class="grow plain">
              <strong>{{ x.p?.name }}</strong>
              <span class="muted small rel">{{ x.p ? relationLabel(x.p.relation) : '' }}{{ x.p?.group ? ` · ${x.p.group}` : '' }}</span>
            </RouterLink>
            <span class="amount">{{ x.r.amount ? formatShort(x.r.amount) : methodLabel(x.r.method) }}</span>
          </li>
        </ul>
      </div>
      <div v-else class="card empty"><p class="muted">{{ q || onlyUnthanked ? '조건에 맞는 사람이 없어요.' : '아직 명단이 없어요.' }}</p></div>
      <p class="muted small hint">체크 = 감사 인사 완료</p>

      <div class="stack actions">
        <RouterLink :to="`/quick?eventId=${event.id}`" class="btn">+ 명단 빠르게 입력</RouterLink>
        <div class="btn-row">
          <RouterLink to="/ocr" class="btn secondary">사진으로 등록</RouterLink>
          <RouterLink :to="`/record?eventId=${event.id}&direction=received`" class="btn secondary">1건 추가</RouterLink>
        </div>
        <RouterLink to="/export" class="btn outline">명단 내보내기 (엑셀·PDF)</RouterLink>
      </div>
    </template>

    <!-- 상대 행사 -->
    <template v-else>
      <div class="card summary">
        <p class="row"><span class="badge accent">{{ ddayLabel(event.date, today) }}</span>
          <RouterLink v-if="owner" :to="`/people/${owner.id}`">{{ owner.name }}</RouterLink>
          <span v-if="owner" class="muted small">{{ relationLabel(owner.relation) }}{{ owner.group ? ` · ${owner.group}` : '' }}</span>
        </p>
        <p class="muted small">알림 {{ event.remind ? '켜짐' : '꺼짐' }}</p>
      </div>

      <h2 class="section-title">보낸 기록</h2>
      <div v-if="given.length" class="card flush">
        <ul class="list">
          <li v-for="r in given" :key="r.id">
            <RouterLink :to="`/record?id=${r.id}`" class="list-row">
              <span class="given amount">{{ directionLabel(r.direction) }} {{ r.amount ? formatShort(r.amount) : '' }}</span>
              <span class="muted small grow">{{ methodLabel(r.method) }}<template v-if="r.attended !== null"> · {{ r.attended ? '참석' : '불참' }}</template></span>
              <span aria-hidden="true">›</span>
            </RouterLink>
          </li>
        </ul>
      </div>
      <p v-else class="muted none">아직 보낸 기록이 없어요.</p>
      <RouterLink :to="`/record?eventId=${event.id}&direction=given`" class="btn add">보냄 기록</RouterLink>

      <template v-if="reference.length">
        <h2 class="section-title">기록 참고</h2>
        <div class="card ref">
          <p v-for="x in reference" :key="x.record.id">
            {{ x.event ? formatDot(x.event.date) : '' }} {{ x.event?.title }}에서 {{ owner?.name }} 님께
            <strong class="received">{{ formatSentence(x.record.amount) }}</strong> 받았어요.
          </p>
        </div>
      </template>

      <button v-if="event.date < today && !given.length" class="btn outline add" @click="toggleNoRecord">
        {{ event.noRecordNeeded ? '홈에 다시 보이기' : '기록 안 함 (홈에서 빼기)' }}
      </button>
    </template>
  </div>
  <div v-else class="page no-tab"><p class="muted">행사를 찾을 수 없어요.</p></div>
</template>

<style scoped>
.summary { margin-top: 14px; }
.summary p { margin: 0 0 4px; }
.big { font-size: 1.15rem; font-weight: 800; }
.tools { margin: 14px 0 10px; display: flex; flex-direction: column; gap: 8px; }
.sort { border: 0; background: none; color: var(--text-2); font-size: 0.88rem; }
.item { padding: 10px 16px; }
.check { width: 22px; height: 22px; accent-color: var(--received); flex: none; }
.plain { text-decoration: none; color: var(--text); }

.hint { margin: 6px 4px 0; }
.actions { margin-top: 18px; }
.none { margin: 0 4px; }
.add { margin-top: 12px; }
.ref p { margin: 0 0 6px; }
.ref p:last-child { margin: 0; }
</style>
