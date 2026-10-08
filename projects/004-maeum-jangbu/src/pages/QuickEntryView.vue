<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AmountPicker from '../components/AmountPicker.vue'
import EventTypePicker from '../components/EventTypePicker.vue'
import { ledger, eventsById, peopleById } from '../lib/store'
import { addEvent, addPerson, addRecord } from '../lib/db'
import { sameName } from '../lib/ledger'
import { formatDot, todayKey } from '../lib/date'
import { formatShort } from '../lib/money'
import { ask } from '../lib/dialog'
import { contactsSupported, pickContactName } from '../lib/contacts'
import { showToast } from '../lib/toast'
import { RELATIONS, defaultEventTitle, relationLabel, type EventType, type Method, type Relation } from '../lib/types'

/**
 * S-08 빠른 연속 입력 (내 행사 명단)
 * 한 사람 = 이름 + 금액 버튼 + [저장하고 다음]. 금액 버튼만으로는 저장하지 않는다 (2026-10-07 결정).
 */
const route = useRoute()
const router = useRouter()
const eventId = ref<string | null>(typeof route.query.eventId === 'string' ? route.query.eventId : null)
const event = computed(() => (eventId.value ? eventsById.value.get(eventId.value) : undefined))

// 행사 고르기 / 만들기
const mineEvents = computed(() => ledger.value.events.filter((e) => e.owner === 'mine').sort((a, b) => b.date.localeCompare(a.date)))
const pick = ref(mineEvents.value[0]?.id ?? 'new')
const newType = ref<EventType>('wedding')
const newCustomType = ref('')
const newKin = ref('')
const newDate = ref(todayKey())
const newPlace = ref('')

async function start() {
  if (pick.value !== 'new') {
    eventId.value = pick.value
  } else {
    if (!newDate.value) return showToast('날짜를 입력해 주세요')
    const e = await addEvent({
      owner: 'mine', personId: null, type: newType.value, customType: newType.value === 'other' ? newCustomType.value.trim() : '',
      title: defaultEventTitle('mine', newType.value, undefined, newCustomType.value, newKin.value),
      date: newDate.value, place: newPlace.value.trim(), remind: false, noRecordNeeded: false,
    })
    eventId.value = e.id
  }
  router.replace({ query: { eventId: eventId.value } })
  await nextTick()
  nameEl.value?.focus()
}

// 입력
const nameEl = ref<HTMLInputElement | null>(null)
const name = ref('')
const relation = ref<Relation>('friend')
const amount = ref<number | null>(null)
const method = ref<Method>('cash')
const added = ref<string[]>([])
const saving = ref(false)

const session = computed(() =>
  added.value
    .map((id) => ledger.value.records.find((r) => r.id === id))
    .filter((r) => !!r)
    .map((r) => ({ r, p: peopleById.value.get(r.personId) })),
)
const sessionTotal = computed(() => session.value.reduce((a, x) => a + x.r.amount, 0))

async function resolvePerson(n: string): Promise<string | null> {
  const same = sameName(ledger.value.people, n)
  if (!same.length) return (await addPerson({ name: n, relation: relation.value, group: '', memo: '' })).id
  const choice = await ask<string>(
    '이미 있는 사람인가요?',
    `"${n}" 이름이 이미 있어요.`,
    [
      ...same.slice(0, 3).map((p) => ({ label: `같은 사람 (${relationLabel(p.relation)}${p.group ? ` · ${p.group}` : ''})`, value: p.id, primary: true })),
      { label: '다른 사람', value: '__new' },
    ],
  )
  if (choice === '__new') return (await addPerson({ name: n, relation: relation.value, group: '', memo: '' })).id
  return choice
}

async function saveNext() {
  if (saving.value || !eventId.value) return
  const n = name.value.trim()
  if (!n) return showToast('이름을 입력해 주세요')
  const noAmountOk = method.value === 'flower' || method.value === 'gift'
  if (amount.value === null && !noAmountOk) return showToast('금액을 골라 주세요')
  saving.value = true
  try {
    const pid = await resolvePerson(n)
    if (!pid) return
    const r = await addRecord({
      eventId: eventId.value, personId: pid, direction: 'received', amount: amount.value ?? 0, method: method.value,
      attended: null, thanked: false, memo: '', source: 'manual',
    })
    added.value = [r.id, ...added.value]
    name.value = ''
    amount.value = null
    showToast(`${n} 저장했어요`, 1200)
  } finally {
    saving.value = false
    await nextTick()
    nameEl.value?.focus()
  }
}

async function fromContacts() {
  try {
    const n = await pickContactName()
    if (n) name.value = n
  } catch (e) {
    showToast(`연락처를 열지 못했어요 (${(e as Error).message})`, 3000)
  }
  nameEl.value?.focus()
}

async function finish() {
  const count = added.value.length
  if (count >= 20) {
    const go = await ask('백업해 둘까요?', `방금 ${count}명을 입력했어요.\n휴대폰을 바꾸거나 앱을 지우면 기록이 사라지니 지금 백업해 두면 안전해요.`, [
      { label: '나중에', value: false, cancel: true },
      { label: '지금 백업하기', value: true, primary: true },
    ])
    if (go) return router.replace('/backup')
  }
  if (eventId.value) router.replace(`/events/${eventId.value}`)
  else router.back()
}
</script>

<template>
  <div class="page no-tab">
    <!-- 1단계: 어느 행사 -->
    <template v-if="!event">
      <h1>어느 행사의 명단인가요?</h1>
      <div class="stack choose">
        <label v-for="e in mineEvents" :key="e.id" class="card row opt">
          <input v-model="pick" type="radio" :value="e.id" /> <span class="grow"><strong>{{ e.title }}</strong><br /><span class="muted small">{{ formatDot(e.date) }}</span></span>
        </label>
        <label class="card row opt">
          <input v-model="pick" type="radio" value="new" /> <strong>새 행사 만들기</strong>
        </label>
      </div>
      <div v-if="pick === 'new'" class="card new-event">
        <span class="label">종류</span>
        <EventTypePicker v-model:type="newType" v-model:custom-type="newCustomType" v-model:kin="newKin" owner="mine" />
        <label class="label" for="qdate">날짜</label>
        <input id="qdate" v-model="newDate" type="date" class="field" />
        <label class="label" for="qplace">장소 <span class="muted small">(선택)</span></label>
        <input id="qplace" v-model="newPlace" class="field" placeholder="예: ○○웨딩홀" />
      </div>
      <button class="btn start" @click="start">입력 시작</button>
    </template>

    <!-- 2단계: 연속 입력 -->
    <template v-else>
      <div class="between head">
        <div>
          <strong>{{ event.title }}</strong>
          <p class="muted small">이번에 입력: {{ added.length }}명 · {{ formatShort(sessionTotal) }}</p>
        </div>
        <button class="btn sm" @click="finish">완료</button>
      </div>

      <form class="card entry" @submit.prevent="saveNext">
        <label class="label" for="qname">이름</label>
        <div class="row">
          <input id="qname" ref="nameEl" v-model="name" class="field grow" autocomplete="off" enterkeyhint="done" placeholder="방명록의 이름" />
          <button v-if="contactsSupported" type="button" class="btn sm secondary" aria-label="연락처에서 고르기" @click="fromContacts">📇</button>
        </div>

        <span class="label">관계 <span class="muted small">(직전 선택 유지)</span></span>
        <div class="chips">
          <button v-for="r in RELATIONS.slice(0, 5)" :key="r.value" type="button" class="chip" :aria-pressed="relation === r.value" @click="relation = r.value">{{ r.label }}</button>
        </div>

        <span class="label">금액</span>
        <AmountPicker v-model="amount" />

        <span class="label">방식 <span class="muted small">(직전 선택 유지)</span></span>
        <div class="chips">
          <button type="button" class="chip" :aria-pressed="method === 'cash'" @click="method = 'cash'">현금</button>
          <button type="button" class="chip" :aria-pressed="method === 'transfer'" @click="method = 'transfer'">계좌</button>
          <button type="button" class="chip" :aria-pressed="method === 'flower'" @click="method = 'flower'">화환</button>
        </div>

        <button class="btn save" type="submit" :disabled="saving">저장하고 다음</button>
      </form>

      <template v-if="session.length">
        <h2 class="section-title">방금 입력한 사람</h2>
        <div class="card flush">
          <ul class="list">
            <li v-for="(x, i) in session" :key="x.r.id">
              <RouterLink :to="`/record?id=${x.r.id}`" class="list-row">
                <span class="muted small num">{{ session.length - i }}</span>
                <span class="grow"><strong>{{ x.p?.name }}</strong> <span class="muted small">{{ x.p ? relationLabel(x.p.relation) : '' }}</span></span>
                <span class="amount">{{ x.r.amount ? formatShort(x.r.amount) : '화환' }}</span>
                <span class="small edit">수정</span>
              </RouterLink>
            </li>
          </ul>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.choose { margin: 14px 0; }
.opt { cursor: pointer; }
.opt input { width: 20px; height: 20px; }
.new-event { background: var(--accent-soft); border-color: transparent; }
.start { margin-top: 18px; }
.head { margin-bottom: 12px; }
.head p { margin: 2px 0 0; }
.entry .label:first-child { margin-top: 0; }
.save { margin-top: 18px; }
.num { width: 22px; }
.edit { color: var(--accent); }
</style>
