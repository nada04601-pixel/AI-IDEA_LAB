<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PersonInput from '../components/PersonInput.vue'
import AmountPicker from '../components/AmountPicker.vue'
import EventTypePicker from '../components/EventTypePicker.vue'
import { ledger, eventsById, peopleById } from '../lib/store'
import { addEvent, addPerson, addRecord, deleteRecord, updateRecord } from '../lib/db'
import { receivedFrom } from '../lib/ledger'
import { formatDot, todayKey } from '../lib/date'
import { formatSentence } from '../lib/money'
import { confirmAsk } from '../lib/dialog'
import { ensureNotifyPermission, notifySupported } from '../lib/notify'
import { showToast } from '../lib/toast'
import {
  METHODS, RELATIONS, defaultEventTitle,
  type Direction, type EventType, type Method, type Relation,
} from '../lib/types'

/**
 * S-07 내역 입력
 * - 기본: 받은 돈 / 보낸 돈 1건
 * - mode=theirs: 상대 경조사 등록 (청첩장·부고만 받은 상태면 금액 없이 저장 가능)
 * - id=: 기존 기록 수정
 */
const route = useRoute()
const router = useRouter()
const q = route.query
const editing = typeof q.id === 'string' ? ledger.value.records.find((r) => r.id === q.id) : undefined
const theirsMode = !editing && q.mode === 'theirs'
const presetEvent = typeof q.eventId === 'string' ? eventsById.value.get(q.eventId) : undefined
const presetEventId = editing?.eventId ?? presetEvent?.id
const presetPersonId =
  editing?.personId ??
  (typeof q.personId === 'string' ? q.personId : undefined) ??
  (presetEvent?.owner === 'theirs' ? (presetEvent.personId ?? undefined) : undefined)
const presetPerson = presetPersonId ? peopleById.value.get(presetPersonId) : undefined

const direction = ref<Direction>(
  editing?.direction ??
    (theirsMode ? 'given' : presetEvent ? (presetEvent.owner === 'mine' ? 'received' : 'given') : q.direction === 'given' ? 'given' : 'received'),
)
const personName = ref(presetPerson?.name ?? '')
const personId = ref<string | null>(presetPerson?.id ?? null)
const newRelation = ref<Relation>('friend')
const newGroup = ref('')

const eventChoice = ref<string>(theirsMode ? 'new' : (presetEventId ?? ''))
const newType = ref<EventType>('wedding')
const newCustomType = ref('')
const newKin = ref('')
const newDate = ref(todayKey())
const newPlace = ref('')
const newRemind = ref(true)

const amount = ref<number | null>(editing ? editing.amount || null : null)
const method = ref<Method>(editing?.method ?? 'cash')
const attended = ref<boolean | null>(editing ? editing.attended : null)
const thanked = ref(editing?.thanked ?? false)
const memo = ref(editing?.memo ?? '')
const saving = ref(false)

const isNewPerson = computed(() => !personId.value && personName.value.trim().length > 0)

const eventOptions = computed(() => {
  const evs = ledger.value.events
  const list =
    direction.value === 'received'
      ? evs.filter((e) => e.owner === 'mine')
      : evs.filter((e) => e.owner === 'theirs' && ((!!personId.value && e.personId === personId.value) || e.id === presetEventId))
  return [...list].sort((a, b) => b.date.localeCompare(a.date))
})

// 고른 사람·방향에 맞는 행사가 없으면 "새 행사"로, 하나뿐이면 그것으로
watch(
  eventOptions,
  (opts) => {
    if (eventChoice.value === 'new') return
    if (opts.some((e) => e.id === eventChoice.value)) return
    eventChoice.value = opts[0]?.id ?? 'new'
  },
  { immediate: true },
)

const reference = computed(() =>
  direction.value === 'given' && personId.value ? receivedFrom(personId.value, ledger.value.records, ledger.value.events).slice(0, 3) : [],
)

const amountRequired = computed(() => !theirsMode && method.value !== 'flower' && method.value !== 'gift')

function setDirection(d: Direction) {
  if (editing) return
  direction.value = d
}

async function save() {
  if (saving.value) return
  const name = personName.value.trim()
  if (!name) return showToast('이름을 입력해 주세요')
  if (eventChoice.value === 'new' && !newDate.value) return showToast('행사 날짜를 입력해 주세요')
  if (!eventChoice.value) return showToast('행사를 골라 주세요')
  if (amountRequired.value && amount.value === null) return showToast('금액을 골라 주세요')
  saving.value = true
  try {
    const pid =
      personId.value ?? (await addPerson({ name, relation: newRelation.value, group: newGroup.value, memo: '' })).id

    let eid = eventChoice.value
    if (eid === 'new') {
      const owner = direction.value === 'received' ? 'mine' : 'theirs'
      const remind = owner === 'theirs' && newRemind.value
      if (remind && notifySupported) await ensureNotifyPermission()
      const e = await addEvent({
        owner,
        personId: owner === 'theirs' ? pid : null,
        type: newType.value,
        customType: newType.value === 'other' ? newCustomType.value.trim() : '',
        title: defaultEventTitle(owner, newType.value, name, newCustomType.value, newKin.value),
        date: newDate.value,
        place: newPlace.value.trim(),
        remind,
        noRecordNeeded: false,
      })
      eid = e.id
    }

    const hasRecord = amount.value !== null || method.value === 'flower' || method.value === 'gift'
    const data = {
      eventId: eid,
      personId: pid,
      direction: direction.value,
      amount: amount.value ?? 0,
      method: method.value,
      attended: attended.value,
      thanked: thanked.value,
      memo: memo.value,
    }
    if (editing) await updateRecord(editing.id, { ...data, memo: data.memo.trim() })
    else if (hasRecord) await addRecord({ ...data, source: 'manual' })

    showToast(theirsMode && !hasRecord ? '경조사를 등록했어요' : '저장했어요')
    if (theirsMode) router.replace(`/events/${eid}`)
    else if (window.history.state?.back) router.back()
    else router.replace('/')
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!editing) return
  if (!(await confirmAsk('기록을 삭제할까요?', '삭제한 기록은 되돌릴 수 없어요.', '삭제'))) return
  await deleteRecord(editing.id)
  showToast('삭제했어요')
  router.back()
}
</script>

<template>
  <div class="page no-tab">
    <h1 v-if="theirsMode" class="mode-title">상대 경조사 등록</h1>

    <div v-if="!theirsMode" class="segment" role="group" aria-label="받음 또는 보냄">
      <button class="received" :aria-pressed="direction === 'received'" :disabled="!!editing && direction !== 'received'" @click="setDirection('received')">받음</button>
      <button class="given" :aria-pressed="direction === 'given'" :disabled="!!editing && direction !== 'given'" @click="setDirection('given')">보냄</button>
    </div>

    <span class="label">{{ theirsMode ? '누구의 경조사인가요?' : '누구와' }}</span>
    <PersonInput v-model:name="personName" v-model:person-id="personId" />
    <template v-if="isNewPerson">
      <p class="muted small new-hint">새 사람으로 추가돼요.</p>
      <div class="chips">
        <button v-for="r in RELATIONS" :key="r.value" type="button" class="chip" :aria-pressed="newRelation === r.value" @click="newRelation = r.value">{{ r.label }}</button>
      </div>
      <input v-model="newGroup" class="field group" placeholder="소속·설명 (선택, 예: 대학 동기)" aria-label="소속" />
    </template>

    <template v-if="!theirsMode">
      <label class="label" for="rev">어떤 행사</label>
      <select id="rev" v-model="eventChoice" class="field">
        <option v-for="e in eventOptions" :key="e.id" :value="e.id">{{ e.title }} · {{ formatDot(e.date) }}</option>
        <option value="new">+ 새 행사</option>
      </select>
    </template>

    <div v-if="eventChoice === 'new'" class="card new-event">
      <span class="label">{{ direction === 'received' ? '내 행사 종류' : '행사 종류' }}</span>
      <EventTypePicker v-model:type="newType" v-model:custom-type="newCustomType" v-model:kin="newKin" :owner="direction === 'received' ? 'mine' : 'theirs'" />
      <label class="label" for="ndate">날짜</label>
      <input id="ndate" v-model="newDate" type="date" class="field" />
      <label class="label" for="nplace">장소 <span class="muted small">(선택)</span></label>
      <input id="nplace" v-model="newPlace" class="field" placeholder="예: ○○웨딩홀" />
      <label v-if="direction === 'given'" class="row remind">
        <input v-model="newRemind" type="checkbox" /> D-day 알림 받기
        <span v-if="!notifySupported" class="badge">앱에서 제공</span>
      </label>
    </div>

    <div v-if="reference.length" class="card ref">
      <strong class="small">기록 참고</strong>
      <p v-for="x in reference" :key="x.record.id">
        {{ x.event ? formatDot(x.event.date) : '' }} {{ x.event?.title }}에서 {{ personName }} 님께
        <strong class="received">{{ formatSentence(x.record.amount) }}</strong> 받았어요.
      </p>
    </div>

    <h2 v-if="theirsMode" class="section-title">보낸 기록 <span class="muted small">(아직 안 보냈으면 비워 두세요)</span></h2>

    <span class="label">금액</span>
    <AmountPicker v-model="amount" />
    <button v-if="!amountRequired && amount !== null" type="button" class="link small" @click="amount = null">금액 지우기</button>

    <span class="label">방식</span>
    <div class="chips">
      <button v-for="m in METHODS" :key="m.value" type="button" class="chip" :aria-pressed="method === m.value" @click="method = m.value">{{ m.label }}</button>
    </div>

    <span class="label">참석</span>
    <div class="chips">
      <button type="button" class="chip" :aria-pressed="attended === true" @click="attended = true">참석</button>
      <button type="button" class="chip" :aria-pressed="attended === false" @click="attended = false">불참</button>
      <button type="button" class="chip" :aria-pressed="attended === null" @click="attended = null">모름</button>
    </div>

    <label v-if="direction === 'received'" class="row thanked">
      <input v-model="thanked" type="checkbox" /> 감사 인사 완료
    </label>

    <label class="label" for="rmemo">메모 <span class="muted small">(선택)</span></label>
    <input id="rmemo" v-model="memo" class="field" placeholder="예: 화환도 보내 줌" />

    <button class="btn save" :disabled="saving" @click="save">저장</button>
    <button v-if="editing" class="btn outline del" @click="remove">기록 삭제</button>
  </div>
</template>

<style scoped>
.mode-title { margin-bottom: 8px; }
.new-hint { margin: 6px 2px; }
.group { margin-top: 8px; }
.new-event { margin-top: 12px; background: var(--accent-soft); border-color: transparent; }
.remind, .thanked { margin-top: 14px; }
.remind input, .thanked input { width: 20px; height: 20px; }
.ref { margin-top: 14px; background: var(--received-soft); border-color: transparent; }
.ref p { margin: 4px 0 0; }
.link { border: 0; background: none; color: var(--accent); padding: 6px 2px; }
.save { margin-top: 24px; }
.del { margin-top: 10px; }
.segment button:disabled { opacity: 0.4; }
</style>
