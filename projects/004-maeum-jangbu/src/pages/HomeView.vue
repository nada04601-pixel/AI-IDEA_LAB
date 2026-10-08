<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ledger, eventsById, loaded, peopleById } from '../lib/store'
import { getSetting, updateEvent } from '../lib/db'
import { backupStatus, type BackupStatus } from '../lib/backup'
import { missingGiven, receivedFrom, upcomingTheirs } from '../lib/ledger'
import { ddayLabel, formatMD, formatShortDay, todayKey } from '../lib/date'
import { formatShort } from '../lib/money'
import { directionLabel, relationLabel } from '../lib/types'
import { getNotifySettings } from '../lib/notify'
import { showToast } from '../lib/toast'

/** S-02 홈 */
const today = todayKey()
const status = ref<BackupStatus>({ kind: 'empty' })
const showAllMissing = ref(false)

async function refreshBackup() {
  const hasData = ledger.value.records.length + ledger.value.events.length > 0
  const days = (await getNotifySettings()).backupDays
  status.value = backupStatus(hasData, await getSetting<number | null>('lastBackupAt', null), await getSetting('changesSinceBackup', 0), Date.now(), days)
}
onMounted(refreshBackup)
watch(ledger, refreshBackup)

const upcoming = computed(() =>
  upcomingTheirs(ledger.value.events, today).slice(0, 3).map((e) => {
    const p = e.personId ? peopleById.value.get(e.personId) : undefined
    const ref0 = p ? receivedFrom(p.id, ledger.value.records, ledger.value.events)[0] : undefined
    const given = ledger.value.records.find((r) => r.eventId === e.id && r.direction === 'given')
    return { e, p, received: ref0?.record.amount, given }
  }),
)

const missing = computed(() => {
  const all = missingGiven(ledger.value.events, ledger.value.records, today).map((e) => {
    const p = e.personId ? peopleById.value.get(e.personId) : undefined
    const ref0 = p ? receivedFrom(p.id, ledger.value.records, ledger.value.events)[0] : undefined
    return { e, p, received: ref0?.record.amount }
  })
  return { list: showAllMissing.value ? all : all.slice(0, 3), total: all.length }
})

const recent = computed(() =>
  [...ledger.value.records]
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 5)
    .map((r) => ({ r, p: peopleById.value.get(r.personId), e: eventsById.value.get(r.eventId) })),
)

async function skip(id: string) {
  await updateEvent(id, { noRecordNeeded: true })
  showToast('목록에서 뺐어요. 행사 화면에서는 계속 볼 수 있어요.', 2600)
}

const lastBackupText = computed(() => {
  if (status.value.kind !== 'ok') return ''
  const d = new Date(status.value.lastAt)
  return `${d.getMonth() + 1}월 ${d.getDate()}일에 백업했어요`
})
</script>

<template>
  <div class="page">
    <!-- 백업 카드 (screens.md S-02 상태 표) -->
    <RouterLink v-if="status.kind === 'never'" to="/backup" class="card backup warn">
      <strong>아직 백업하지 않았어요</strong>
      <span class="muted small">휴대폰을 바꾸거나 앱을 지우면 기록이 사라져요.</span>
      <span class="btn sm">지금 백업하기</span>
    </RouterLink>
    <RouterLink v-else-if="status.kind === 'overdue'" to="/backup" class="card backup warn">
      <strong>⚠ 마지막 백업 {{ status.days }}일 전</strong>
      <span class="muted small">그 뒤로 {{ status.changes }}건이 추가·수정됐어요.</span>
      <span class="btn sm">지금 백업하기</span>
    </RouterLink>
    <RouterLink v-else-if="status.kind === 'ok'" to="/backup" class="backup-ok muted small">✓ {{ lastBackupText }}</RouterLink>

    <template v-if="loaded && !ledger.records.length && !ledger.events.length">
      <div class="card empty">
        <p><strong>아직 기록이 없어요</strong></p>
        <p class="muted">지난 기록이 사진으로 남아 있다면 한 번에 옮길 수 있어요.</p>
        <div class="stack">
          <RouterLink to="/quick" class="btn">내 행사 명단 입력하기</RouterLink>
          <RouterLink to="/record?mode=theirs" class="btn secondary">받은 청첩장·부고 등록</RouterLink>
          <RouterLink to="/ocr" class="btn outline">사진으로 지난 기록 등록</RouterLink>
        </div>
      </div>
    </template>

    <h2 class="section-title">다가오는 경조사</h2>
    <div v-if="upcoming.length" class="card flush">
      <ul class="list">
        <li v-for="u in upcoming" :key="u.e.id">
          <div class="list-row">
            <RouterLink :to="`/events/${u.e.id}`" class="grow plain">
              <span class="row"><span class="badge accent">{{ ddayLabel(u.e.date, today) }}</span> <strong>{{ u.e.title }}</strong></span>
              <span class="muted small">
                {{ formatShortDay(u.e.date) }}
                <template v-if="u.p"> · {{ relationLabel(u.p.relation) }}</template>
                <template v-if="u.received !== undefined"> · <span class="received">받음 {{ formatShort(u.received) }}</span></template>
              </span>
            </RouterLink>
            <span v-if="u.given" class="given small amount">보냄 {{ formatShort(u.given.amount) }}</span>
            <RouterLink v-else :to="`/record?eventId=${u.e.id}&direction=given`" class="btn sm secondary">보냄 기록</RouterLink>
          </div>
        </li>
      </ul>
    </div>
    <p v-else class="muted none">예정된 경조사가 없어요. 청첩장이나 부고를 받으면 [+ 기록]에서 등록해 주세요.</p>

    <template v-if="missing.total">
      <h2 class="section-title">기록이 비어 있는 경조사</h2>
      <div class="card flush">
        <ul class="list">
          <li v-for="m in missing.list" :key="m.e.id" class="missing">
            <RouterLink :to="`/events/${m.e.id}`" class="plain">
              <strong>{{ formatMD(m.e.date) }} {{ m.e.title }}</strong>
              <span class="muted small">
                <template v-if="m.p">{{ relationLabel(m.p.relation) }}</template>
                <template v-if="m.received !== undefined"> · 받음 {{ formatShort(m.received) }}</template>
              </span>
            </RouterLink>
            <div class="btn-row">
              <button class="btn sm outline" @click="skip(m.e.id)">기록 안 함</button>
              <RouterLink :to="`/record?eventId=${m.e.id}&direction=given`" class="btn sm secondary">보냄 기록</RouterLink>
            </div>
          </li>
        </ul>
        <button v-if="missing.total > 3 && !showAllMissing" class="list-row more" @click="showAllMissing = true">
          {{ missing.total - 3 }}개 더 보기
        </button>
      </div>
    </template>

    <template v-if="recent.length">
      <div class="between">
        <h2 class="section-title">최근 기록</h2>
        <RouterLink to="/records" class="small">전체 보기</RouterLink>
      </div>
      <div class="card flush">
        <ul class="list">
          <li v-for="x in recent" :key="x.r.id">
            <RouterLink :to="`/record?id=${x.r.id}`" class="list-row">
              <span class="grow">
                <strong>{{ x.p?.name }}</strong>
                <span class="muted small"> · {{ x.e?.title }}</span>
              </span>
              <span :class="x.r.direction" class="amount">{{ directionLabel(x.r.direction) }} {{ x.r.amount ? formatShort(x.r.amount) : '' }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.backup { display: flex; flex-direction: column; gap: 4px; text-decoration: none; color: var(--text); margin-bottom: 4px; }
.backup .btn { align-self: flex-end; margin-top: 6px; }
.warn { background: var(--warn-soft); border-color: transparent; }
.backup-ok { display: block; text-decoration: none; padding: 2px 4px; }
.plain { text-decoration: none; color: var(--text); display: flex; flex-direction: column; gap: 2px; }
.none { margin: 0 4px; }
.missing { padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
.missing .btn-row { justify-content: flex-end; }
.missing .btn-row > * { flex: 0 0 auto; }
.more { justify-content: center; color: var(--accent); font-weight: 700; border-top: 1px solid var(--line); }
</style>
