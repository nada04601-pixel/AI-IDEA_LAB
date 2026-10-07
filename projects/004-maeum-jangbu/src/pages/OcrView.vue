<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EventTypePicker from '../components/EventTypePicker.vue'
import { ledger, eventsById } from '../lib/store'
import { addEvent, addPerson, addRecord } from '../lib/db'
import { deleteCapturedPhotos, ocrSupported, prepareImage, recognize, type PreparedImage } from '../lib/ocr'
import { parseTransferLines } from '../lib/ocrParse'
import { checkedSummary, draftRows, type DraftRow } from '../lib/ocrImport'
import { formatDot, todayKey } from '../lib/date'
import { formatFull, formatShort, parseAmount } from '../lib/money'
import { ask } from '../lib/dialog'
import { showToast } from '../lib/toast'
import { defaultEventTitle, relationLabel, type Direction, type EventType } from '../lib/types'

/**
 * S-09 사진으로 등록 → S-10 인식 결과 확인
 * 사진은 휴대폰 안에서만 읽고 저장하지 않는다. 결과는 확인한 줄만 등록한다.
 */
const route = useRoute()
const router = useRouter()
const today = todayKey()

// ── S-09 준비 ──
const presetEvent = typeof route.query.eventId === 'string' ? eventsById.value.get(route.query.eventId) : undefined
const direction = ref<Direction>('received')
const mineEvents = computed(() => ledger.value.events.filter((e) => e.owner === 'mine').sort((a, b) => b.date.localeCompare(a.date)))
const eventChoice = ref<string>(presetEvent?.owner === 'mine' ? presetEvent.id : (mineEvents.value[0]?.id ?? 'new'))
const newType = ref<EventType>('wedding')
const newCustomType = ref('')
const newDate = ref(today)
/** 보냄: 사람마다 만들 상대 행사의 종류 */
const givenType = ref<EventType>('wedding')
const givenCustomType = ref('')

const fileInput = ref<HTMLInputElement | null>(null)
const cameraInput = ref<HTMLInputElement | null>(null)
const images = shallowRef<PreparedImage[]>([])
const reading = ref<{ done: number; total: number } | null>(null)
const error = ref<string | null>(null)

async function onFiles(ev: Event) {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  const room = 20 - images.value.length
  if (files.length > room) showToast(`사진은 한 번에 20장까지예요`, 2500)
  const added: PreparedImage[] = []
  for (const f of files.slice(0, Math.max(0, room))) {
    try {
      added.push(await prepareImage(f))
    } catch {
      showToast('열 수 없는 사진이 있어 뺐어요', 2500)
    }
  }
  images.value = [...images.value, ...added]
  // 줄인 사진은 메모리에만 두고, 카메라 앱이 남긴 원본 파일은 바로 지운다
  if (input === cameraInput.value) void deleteCapturedPhotos()
}

onBeforeUnmount(() => void deleteCapturedPhotos())

function removeImage(i: number) {
  images.value = images.value.filter((_, k) => k !== i)
}

// ── S-10 확인 ──
const rows = ref<DraftRow[] | null>(null)
const unmatched = ref<string[]>([])
const current = ref(0)
const selected = ref<string | null>(null)
const onlyCheck = ref(false)
const saving = ref(false)

const summary = computed(() => (rows.value ? checkedSummary(rows.value) : { count: 0, total: 0 }))
const shownRows = computed(() => (rows.value ?? []).filter((r) => !onlyCheck.value || r.note || r.flags.length))
const selectedRow = computed(() => rows.value?.find((r) => r.key === selected.value && r.image === current.value) ?? null)

async function read() {
  if (!images.value.length) return
  error.value = null
  reading.value = { done: 0, total: images.value.length }
  const all: (ReturnType<typeof parseTransferLines>['rows'][number] & { image: number })[] = []
  const missed: string[] = []
  try {
    for (const [i, img] of images.value.entries()) {
      const lines = await recognize(img)
      const parsed = parseTransferLines(lines, today)
      all.push(...parsed.rows.map((r) => ({ ...r, image: i })))
      missed.push(...parsed.unmatched)
      reading.value = { done: i + 1, total: images.value.length }
    }
  } catch (e) {
    error.value = `글자를 읽지 못했어요. (${(e as Error).message})`
    reading.value = null
    return
  }
  reading.value = null
  if (!all.length) {
    error.value = '사진에서 이름과 금액을 찾지 못했어요. 이체 내역 화면 전체가 잘 보이게 캡처한 사진인지 확인해 주세요.'
    return
  }
  rows.value = draftRows(all, ledger.value, { direction: direction.value, eventId: direction.value === 'received' && eventChoice.value !== 'new' ? eventChoice.value : undefined })
  unmatched.value = missed
  current.value = all[0].image
}

const wrapEl = ref<HTMLElement | null>(null)

/** 줄을 고르면 원본 사진에서 그 위치를 보여 준다 */
async function select(r: DraftRow) {
  selected.value = r.key
  current.value = r.image
  await nextTick()
  const wrap = wrapEl.value
  if (!wrap) return
  const stageH = wrap.scrollHeight
  const y = (r.box.top / images.value[r.image].height) * stageH
  wrap.scrollTo({ top: Math.max(0, y - wrap.clientHeight / 3), behavior: 'smooth' })
}

function setAmount(r: DraftRow, text: string) {
  const v = parseAmount(text)
  if (v !== null) r.amount = v
}

/** 원본 사진 위에 표시할 강조 영역 (%) */
function boxStyle(r: DraftRow) {
  const img = images.value[r.image]
  const pad = 6
  return {
    left: `${((r.box.left - pad) / img.width) * 100}%`,
    top: `${((r.box.top - pad) / img.height) * 100}%`,
    width: `${((r.box.right - r.box.left + pad * 2) / img.width) * 100}%`,
    height: `${((r.box.bottom - r.box.top + pad * 2) / img.height) * 100}%`,
  }
}

const sameNamePeople = (name: string) => ledger.value.people.filter((p) => p.name === name.trim())

async function register() {
  if (!rows.value || saving.value) return
  const list = rows.value.filter((r) => r.checked)
  if (!list.length) return showToast('등록할 줄을 골라 주세요')
  if (list.some((r) => !r.name.trim())) return showToast('이름이 빈 줄이 있어요')
  saving.value = true
  try {
    let eventId = direction.value === 'received' && eventChoice.value !== 'new' ? eventChoice.value : null
    if (direction.value === 'received' && !eventId) {
      eventId = (await addEvent({
        owner: 'mine', personId: null, type: newType.value, customType: newType.value === 'other' ? newCustomType.value.trim() : '',
        title: defaultEventTitle('mine', newType.value, undefined, newCustomType.value), date: newDate.value || today,
        place: '', remind: false, noRecordNeeded: false,
      })).id
    }
    // 같은 이름·소속의 새 사람, 같은 사람·날짜의 상대 행사는 한 번만 만든다
    // (저장 직후 화면 데이터가 다시 읽히기 전이라 여기서 따로 기억한다)
    const created = new Map<string, string>()
    const createdEvents = new Map<string, string>()
    for (const r of list) {
      let pid = r.personId
      if (!pid) {
        const key = `${r.name.trim()}|${r.group.trim()}`
        pid = created.get(key) ?? (await addPerson({ name: r.name, relation: 'other', group: r.group, memo: '' })).id
        created.set(key, pid)
      }
      let eid = eventId
      if (direction.value === 'given') {
        // 보냄: 그 사람의 같은 날 상대 행사가 있으면 거기에, 없으면 새로
        const date = r.date ?? today
        const found = createdEvents.get(`${pid}|${date}`) ?? ledger.value.events.find((e) => e.owner === 'theirs' && e.personId === pid && e.date === date)?.id
        eid = found ?? (await addEvent({
          owner: 'theirs', personId: pid, type: givenType.value, customType: givenType.value === 'other' ? givenCustomType.value.trim() : '',
          title: defaultEventTitle('theirs', givenType.value, r.name.trim(), givenCustomType.value), date, place: '',
          remind: false, noRecordNeeded: false,
        })).id
        createdEvents.set(`${pid}|${date}`, eid)
      }
      await addRecord({
        eventId: eid!, personId: pid, direction: direction.value, amount: r.amount, method: 'transfer',
        attended: null, thanked: false, memo: r.date ? `이체 ${formatDot(r.date)}` : '', source: 'ocr',
      })
    }
    images.value = []
    rows.value = null
    showToast(`${list.length}건을 등록했어요`)
    const go = await ask('백업해 둘까요?', `사진으로 ${list.length}건을 등록했어요.\n휴대폰을 바꾸거나 앱을 지우면 기록이 사라지니 지금 백업해 두면 안전해요.`, [
      { label: '나중에', value: false },
      { label: '지금 백업하기', value: true, primary: true },
    ])
    if (go) router.replace('/backup')
    else router.replace(direction.value === 'received' ? `/events/${eventId}` : '/events?tab=theirs')
  } finally {
    saving.value = false
  }
}

const flagText: Record<string, string> = {
  'name-split': '이름과 소속을 나눠 봤어요. 맞는지 확인해 주세요',
  'name-check': '이름을 확인해 주세요',
  'amount-check': '금액을 확인해 주세요',
}
</script>

<template>
  <div class="page no-tab">
    <div v-if="!ocrSupported" class="card empty">
      <p><strong>안드로이드 앱에서 쓸 수 있어요</strong></p>
      <p class="muted">웹 버전에서는 사진 속 글자를 읽을 수 없어요.</p>
      <RouterLink to="/quick" class="btn secondary">명단 빠르게 입력하기</RouterLink>
    </div>

    <!-- S-09 사진으로 등록 -->
    <template v-else-if="!rows">
      <span class="label">받은 돈인가요, 보낸 돈인가요?</span>
      <div class="segment" role="group">
        <button class="received" :aria-pressed="direction === 'received'" @click="direction = 'received'">받음 (입금)</button>
        <button class="given" :aria-pressed="direction === 'given'" @click="direction = 'given'">보냄 (출금)</button>
      </div>

      <template v-if="direction === 'received'">
        <label class="label" for="oev">어떤 행사에 받은 돈인가요?</label>
        <select id="oev" v-model="eventChoice" class="field">
          <option v-for="e in mineEvents" :key="e.id" :value="e.id">{{ e.title }} · {{ formatDot(e.date) }}</option>
          <option value="new">+ 새 행사</option>
        </select>
        <div v-if="eventChoice === 'new'" class="card new-event">
          <EventTypePicker v-model:type="newType" v-model:custom-type="newCustomType" />
          <label class="label" for="odate">날짜</label>
          <input id="odate" v-model="newDate" type="date" class="field" />
        </div>
      </template>
      <template v-else>
        <span class="label">어떤 경조사에 보낸 돈인가요?</span>
        <EventTypePicker v-model:type="givenType" v-model:custom-type="givenCustomType" />
        <p class="muted small hint">사람마다 이체한 날짜로 상대 경조사를 만들어요. (같은 날 경조사가 이미 있으면 거기에 넣어요)</p>
      </template>

      <span class="label">사진 <span class="muted small">({{ images.length }}/20)</span></span>
      <div class="thumbs">
        <div v-for="(img, i) in images" :key="i" class="thumb">
          <img :src="img.url" :alt="`사진 ${i + 1}`" />
          <button class="x" :aria-label="`사진 ${i + 1} 빼기`" @click="removeImage(i)">✕</button>
        </div>
      </div>
      <div v-if="images.length < 20" class="btn-row pickers">
        <button class="btn secondary" @click="cameraInput?.click()">📷 촬영</button>
        <button class="btn secondary" @click="fileInput?.click()">🖼 앨범에서 선택</button>
      </div>
      <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="onFiles" />
      <!-- capture: 앱에서는 기본 카메라 앱이 바로 열린다 (카메라 권한 불필요) -->
      <input ref="cameraInput" type="file" accept="image/*" capture="environment" hidden @change="onFiles" />

      <div class="card tips">
        <p class="small"><strong>잘 읽히는 사진</strong></p>
        <ul class="small muted">
          <li>✓ 은행 앱 이체 내역 화면 캡처</li>
          <li>✓ 엑셀·메모 화면 캡처, 인쇄된 대장</li>
          <li>△ 손글씨 장부·봉투 (지금은 잘 못 읽어요)</li>
        </ul>
        <p class="small muted">사진은 휴대폰 안에서만 읽고, 저장하거나 보내지 않아요.</p>
      </div>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="btn go" :disabled="!images.length || !!reading" @click="read">
        {{ reading ? `글자를 읽고 있어요… ${reading.done} / ${reading.total}` : `글자 읽기 (${images.length}장)` }}
      </button>
    </template>

    <!-- S-10 인식 결과 확인 -->
    <template v-else>
      <div class="viewer card flush">
        <div ref="wrapEl" class="imgwrap">
          <!-- 강조 영역은 사진 크기 기준(%)으로 놓기 위해 사진과 같은 크기의 stage 안에 둔다 -->
          <div class="stage">
            <img :src="images[current].url" alt="원본 사진" />
            <div v-if="selectedRow" class="hl" :style="boxStyle(selectedRow)" />
          </div>
        </div>
        <div v-if="images.length > 1" class="between pager">
          <button class="chip" :disabled="current === 0" @click="current--">◀</button>
          <span class="small">사진 {{ current + 1 }} / {{ images.length }}</span>
          <button class="chip" :disabled="current === images.length - 1" @click="current++">▶</button>
        </div>
      </div>

      <div class="card sum">
        <strong>{{ rows.length }}줄 읽음 · {{ summary.count }}건 등록 예정</strong>
        <span class="big">합계 {{ formatFull(summary.total) }}</span>
        <label class="row small"><input v-model="onlyCheck" type="checkbox" /> 확인이 필요한 줄만 보기</label>
      </div>
      <p v-if="unmatched.length" class="muted small">금액을 찾지 못한 글자: {{ unmatched.slice(0, 5).join(', ') }}</p>

      <ul class="list rows">
        <li v-for="r in shownRows" :key="`${r.image}-${r.key}`" class="card row-item" :class="{ off: !r.checked, sel: selected === r.key && current === r.image }" @click="select(r)">
          <div class="row top">
            <input v-model="r.checked" type="checkbox" class="chk" :aria-label="`${r.name} 등록`" @click.stop />
            <input v-model="r.name" class="field nm" aria-label="이름" @focus="select(r)" />
            <input :value="r.amount.toLocaleString('ko-KR')" class="field amt" inputmode="numeric" aria-label="금액" @focus="select(r)" @change="setAmount(r, ($event.target as HTMLInputElement).value)" />
          </div>
          <div class="row meta small">
            <span :class="r.direction" class="dir">{{ r.direction === 'received' ? '입금' : '출금' }}</span>
            <span v-if="r.date" class="muted">{{ formatDot(r.date) }}</span>
            <input v-model="r.group" class="field grp" placeholder="소속 (선택)" aria-label="소속" @focus="select(r)" />
          </div>
          <select v-if="sameNamePeople(r.name).length" v-model="r.personId" class="field who small" aria-label="같은 사람 고르기" @click.stop>
            <option :value="null">새 사람으로 추가</option>
            <option v-for="p in sameNamePeople(r.name)" :key="p.id" :value="p.id">기존 {{ p.name }} · {{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</option>
          </select>
          <p v-if="r.note" class="note small">ⓘ {{ r.note }}</p>
          <p v-for="f in r.flags" :key="f" class="warn small">⚠ {{ flagText[f] }}</p>
          <p class="raw small muted">읽은 글자: {{ r.raw }}</p>
        </li>
      </ul>

      <button class="btn go" :disabled="saving || !summary.count" @click="register">
        {{ summary.count ? `${summary.count}건 등록 · ${formatShort(summary.total)}` : '등록할 줄을 골라 주세요' }}
      </button>
      <button class="btn outline back" @click="rows = null">사진 다시 고르기</button>
      <p v-if="direction === 'received'" class="muted small center">
        {{ eventChoice === 'new' ? '새 행사' : eventsById.get(eventChoice)?.title }}에 받은 돈으로 등록해요. 이름이 처음 나온 사람은 관계 "기타"로 추가돼요.
      </p>
      <p v-else class="muted small center">사람마다 이체한 날짜의 상대 경조사에 보낸 돈으로 등록해요.</p>
    </template>
  </div>
</template>

<style scoped>
.new-event { margin-top: 12px; background: var(--accent-soft); border-color: transparent; }
.hint { margin: 8px 2px 0; }
.thumbs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.thumb { position: relative; aspect-ratio: 3 / 5; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); background: var(--surface); }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb .x { position: absolute; top: 4px; right: 4px; width: 26px; height: 26px; border-radius: 50%; border: 0; background: rgb(0 0 0 / 0.55); color: #fff; font-size: 0.8rem; }
.pickers { margin-top: 10px; }
.tips { margin-top: 14px; }
.tips p { margin: 0 0 4px; }
.tips ul { margin: 0 0 6px; padding-left: 18px; }
.error { color: var(--warn); background: var(--warn-soft); padding: 10px 12px; border-radius: 10px; margin-top: 12px; }
.go { margin-top: 16px; }
.back { margin-top: 8px; }
.center { text-align: center; }

.viewer { position: sticky; top: 64px; z-index: 5; }
.imgwrap { max-height: 34vh; overflow: auto; }
.stage { position: relative; }
.imgwrap img { display: block; width: 100%; }
.hl { position: absolute; border: 3px solid var(--accent); border-radius: 6px; background: rgb(140 106 79 / 0.15); pointer-events: none; }
.pager { padding: 6px 10px; }
.sum { margin-top: 12px; display: flex; flex-direction: column; gap: 4px; }
.sum .big { font-size: 1.15rem; font-weight: 800; }
.sum input { width: 18px; height: 18px; }
.rows { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.rows > li + li { border-top: 1px solid var(--line); }
.row-item { padding: 10px 12px; cursor: pointer; }
.row-item.off { opacity: 0.6; }
.row-item.sel { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.chk { width: 22px; height: 22px; flex: none; }
.nm { flex: 1; min-width: 0; padding: 8px 10px; font-weight: 700; }
.amt { width: 120px; padding: 8px 10px; text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; }
.meta { margin-top: 6px; gap: 8px; padding-left: 30px; }
.dir { font-weight: 700; }
.grp { flex: 1; min-width: 0; padding: 6px 8px; }
.who { margin: 6px 0 0 30px; width: calc(100% - 30px); padding: 6px 8px; }
.note, .warn, .raw { margin: 6px 0 0 30px; }
.note { color: var(--text-2); }
.warn { color: var(--warn); }
</style>
