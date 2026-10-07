<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ledger, eventsById, peopleById } from '../lib/store'
import { RECORD_COLUMNS, recordRows, scopeData, toCsv, type Scope } from '../lib/sheet'
import { shareFile } from '../lib/share'
import { ask } from '../lib/dialog'
import { formatDot, todayKey } from '../lib/date'
import { formatShort } from '../lib/money'
import { isNativeApp } from '../lib/platform'
import { relationLabel } from '../lib/types'

/** S-11 보기 좋은 파일로 내보내기: 엑셀 / CSV / PDF 명단 */
const route = useRoute()
const router = useRouter()
const presetEvent = typeof route.query.eventId === 'string' ? eventsById.value.get(route.query.eventId) : undefined

const format = ref<'xlsx' | 'csv' | 'pdf'>(route.query.format === 'pdf' ? 'pdf' : 'xlsx')
const kind = ref<Scope['kind']>(presetEvent ? 'event' : 'all')
const eventId = ref(presetEvent?.id ?? '')
const personId = ref('')
const from = ref(`${todayKey().slice(0, 4)}-01-01`)
const to = ref(todayKey())
const busy = ref(false)
const message = ref<string | null>(null)

const events = computed(() => [...ledger.value.events].sort((a, b) => b.date.localeCompare(a.date)))
const mineEvents = computed(() => events.value.filter((e) => e.owner === 'mine'))
const people = computed(() => [...ledger.value.people].sort((a, b) => a.name.localeCompare(b.name, 'ko')))

const scope = computed<Scope | null>(() => {
  if (kind.value === 'all') return { kind: 'all' }
  if (kind.value === 'event') return eventId.value ? { kind: 'event', eventId: eventId.value } : null
  if (kind.value === 'person') return personId.value ? { kind: 'person', personId: personId.value } : null
  return from.value && to.value && from.value <= to.value ? { kind: 'period', from: from.value, to: to.value } : null
})
const picked = computed(() => (scope.value ? scopeData(ledger.value, scope.value) : null))
const total = computed(() => picked.value?.records.reduce((s, r) => s + (r.direction === 'received' ? r.amount : 0), 0) ?? 0)

function setFormat(f: 'xlsx' | 'csv' | 'pdf') {
  format.value = f
  message.value = null
  // PDF 명단은 내 행사 하나 단위
  if (f === 'pdf') {
    kind.value = 'event'
    if (!mineEvents.value.some((e) => e.id === eventId.value)) eventId.value = mineEvents.value[0]?.id ?? ''
  }
}

const safe = (s: string) => s.replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim()
function fileBase(): string {
  const s = scope.value!
  if (s.kind === 'event') return `마음장부_${safe(eventsById.value.get(s.eventId)?.title ?? '행사')}_명단`
  if (s.kind === 'person') return `마음장부_${safe(peopleById.value.get(s.personId)?.name ?? '사람')}`
  if (s.kind === 'period') return `마음장부_${s.from}~${s.to}`
  return `마음장부_전체_${todayKey()}`
}

async function run() {
  if (!scope.value || !picked.value) return
  message.value = null
  // PDF는 명단 화면의 [PDF로 저장]에서 안내한다
  if (format.value === 'pdf') return router.push(`/events/${eventId.value}/print`)
  // 비밀번호를 걸 수 없는 형식이라 매번 안내 (screens.md S-11, 2026-10-07 결정)
  const ok = await ask('내보낼까요?', '이 파일에는 이름과 금액이 그대로 들어 있어요.\n카카오톡·이메일로 보내면 파일을 받은 사람도 볼 수 있어요.', [
    { label: '취소', value: false },
    { label: '내보내기', value: true, primary: true },
  ])
  if (!ok) return

  busy.value = true
  try {
    let res
    if (format.value === 'csv') {
      res = await shareFile(`${fileBase()}.csv`, toCsv(RECORD_COLUMNS, recordRows(picked.value)), 'text/csv', '마음장부 CSV')
    } else {
      const { buildWorkbook } = await import('../lib/excel')
      const bytes = await buildWorkbook(picked.value, fileBase())
      res = await shareFile(`${fileBase()}.xlsx`, bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '마음장부 엑셀')
    }
    message.value = res === 'canceled' ? '내보내기를 취소했어요.' : isNativeApp ? '파일을 만들었어요. 고른 곳에 잘 저장됐는지 확인해 주세요.' : '파일을 내려받았어요.'
  } catch (e) {
    message.value = `파일을 만들지 못했어요. (${(e as Error).message})`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page no-tab">
    <span class="label">형식</span>
    <div class="segment" role="group" aria-label="형식">
      <button :aria-pressed="format === 'xlsx'" @click="setFormat('xlsx')">엑셀</button>
      <button :aria-pressed="format === 'csv'" @click="setFormat('csv')">CSV</button>
      <button :aria-pressed="format === 'pdf'" @click="setFormat('pdf')">PDF 명단</button>
    </div>
    <p class="muted small desc">
      <template v-if="format === 'xlsx'">시트 3종: 전체 내역 · 사람별 장부 · 행사별 명단. 금액은 숫자라 엑셀에서 바로 합계·정렬할 수 있어요. PC에서 고친 뒤 다시 가져올 수도 있어요.</template>
      <template v-else-if="format === 'csv'">전체 내역을 CSV로 내보내요. 다른 앱이나 구글 시트로 옮길 때 써요.</template>
      <template v-else>내 행사의 답례 명단을 A4로 정리해요. 인쇄 화면에서 "PDF로 저장"을 고르면 PDF가 돼요.</template>
    </p>

    <template v-if="format !== 'pdf'">
      <span class="label">범위</span>
      <div class="chips">
        <button class="chip" :aria-pressed="kind === 'all'" @click="kind = 'all'">전체</button>
        <button class="chip" :aria-pressed="kind === 'event'" @click="kind = 'event'">행사별</button>
        <button class="chip" :aria-pressed="kind === 'period'" @click="kind = 'period'">기간</button>
        <button class="chip" :aria-pressed="kind === 'person'" @click="kind = 'person'">사람</button>
      </div>
    </template>

    <select v-if="kind === 'event'" v-model="eventId" class="field pick" aria-label="행사">
      <option value="" disabled>행사 고르기</option>
      <option v-for="e in format === 'pdf' ? mineEvents : events" :key="e.id" :value="e.id">{{ e.title }} · {{ formatDot(e.date) }}</option>
    </select>
    <select v-if="kind === 'person'" v-model="personId" class="field pick" aria-label="사람">
      <option value="" disabled>사람 고르기</option>
      <option v-for="p in people" :key="p.id" :value="p.id">{{ p.name }} · {{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</option>
    </select>
    <div v-if="kind === 'period'" class="row pick">
      <input v-model="from" type="date" class="field" aria-label="시작일" />
      <span>~</span>
      <input v-model="to" type="date" class="field" aria-label="종료일" />
    </div>

    <div v-if="picked" class="card summary">
      <template v-if="format === 'pdf'">명단 {{ picked.records.filter((r) => r.direction === 'received').length }}명 · {{ formatShort(total) }}</template>
      <template v-else>기록 {{ picked.records.length }}건 · 사람 {{ picked.people.length }}명</template>
    </div>
    <p v-if="format === 'pdf' && !mineEvents.length" class="muted">내 행사가 아직 없어요.</p>

    <button class="btn run" :disabled="busy || !picked || !picked.records.length" @click="run">
      {{ busy ? '만드는 중…' : format === 'pdf' ? '명단 보기 · PDF 저장' : '내보내기' }}
    </button>
    <p v-if="picked && !picked.records.length" class="muted small center">내보낼 기록이 없어요.</p>
    <p v-if="message" class="msg" role="status">{{ message }}</p>
    <p class="muted small note">엑셀·CSV·PDF에는 비밀번호를 걸 수 없어요. 전체를 안전하게 보관하려면 <RouterLink to="/backup">백업 파일</RouterLink>을 쓰세요.</p>
  </div>
</template>

<style scoped>
.desc { margin: 8px 2px 0; }
.pick { margin-top: 12px; }
.summary { margin-top: 14px; font-weight: 700; }
.run { margin-top: 18px; }
.center { text-align: center; }
.msg { font-weight: 600; margin-top: 12px; }
.note { margin-top: 18px; }
</style>
