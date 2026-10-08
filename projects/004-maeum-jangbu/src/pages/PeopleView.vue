<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ledger } from '../lib/store'
import { deletePeople, setRelation } from '../lib/db'
import { showToast } from '../lib/toast'
import { confirmAsk } from '../lib/dialog'
import { onBack } from '../lib/back'
import { diffShort, totalsByPerson } from '../lib/ledger'
import { formatShort } from '../lib/money'
import { RELATIONS, relationLabel, type Relation } from '../lib/types'

/** S-03 사람 목록 */
const q = ref('')
const relation = ref<Relation | 'all'>('all')
const sort = ref<'recent' | 'name' | 'received' | 'diff'>('recent')

// 여러 명 골라 관계 한꺼번에 바꾸기·삭제 (사진·연락처로 들어온 사람은 관계가 "기타")
const selecting = ref(false)
const picked = ref(new Set<string>())
const newRelation = ref<Relation>('friend')
const saving = ref(false)

function startSelect() {
  selecting.value = true
  picked.value = new Set()
}
function stopSelect() {
  selecting.value = false
  picked.value = new Set()
}
function togglePick(id: string) {
  const s = new Set(picked.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  picked.value = s
}
const allShownPicked = computed(() => rows.value.length > 0 && rows.value.every((x) => picked.value.has(x.p.id)))
function toggleAllShown() {
  const s = new Set(picked.value)
  const on = !allShownPicked.value
  for (const x of rows.value) (on ? s.add(x.p.id) : s.delete(x.p.id))
  picked.value = s
}
async function applyRelation() {
  if (!picked.value.size || saving.value) return
  saving.value = true
  try {
    const n = await setRelation([...picked.value], newRelation.value)
    showToast(`${n}명을 "${relationLabel(newRelation.value)}"(으)로 바꿨어요`, 2400)
    stopSelect()
  } finally {
    saving.value = false
  }
}

async function removePicked() {
  if (!picked.value.size || saving.value) return
  const ids = picked.value
  const recordCount = ledger.value.records.filter((r) => ids.has(r.personId)).length
  const eventCount = ledger.value.events.filter((e) => e.owner === 'theirs' && e.personId && ids.has(e.personId)).length
  const detail = [recordCount && `기록 ${recordCount}건`, eventCount && `경조사 ${eventCount}개`].filter(Boolean).join(', ')
  const ok = await confirmAsk(
    `${ids.size}명을 삭제할까요?`,
    `${detail ? `이 사람들의 ${detail}도 함께 지워져요. ` : ''}삭제하면 되돌릴 수 없어요.`,
    '삭제',
  )
  if (!ok) return
  saving.value = true
  try {
    const n = await deletePeople([...ids])
    showToast(`${n}명을 삭제했어요`)
    stopSelect()
  } finally {
    saving.value = false
  }
}

// 선택 중에 뒤로가기 → 선택만 끝낸다
const offBack = onBack(() => {
  if (!selecting.value) return false
  stopSelect()
  return true
})
onBeforeUnmount(offBack)

const totals = computed(() => totalsByPerson(ledger.value.records))
const lastActivity = computed(() => {
  const m = new Map<string, number>()
  for (const r of ledger.value.records) m.set(r.personId, Math.max(m.get(r.personId) ?? 0, r.updatedAt))
  return m
})

const rows = computed(() => {
  const s = q.value.trim()
  const list = ledger.value.people
    .filter((p) => relation.value === 'all' || p.relation === relation.value)
    .filter((p) => !s || p.name.includes(s) || p.group.includes(s))
    .map((p) => {
      const t = totals.value.get(p.id) ?? { received: 0, given: 0, receivedCount: 0, givenCount: 0 }
      return { p, t, diff: diffShort(t), last: lastActivity.value.get(p.id) ?? p.updatedAt }
    })
  const by = {
    recent: (a: (typeof list)[0], b: (typeof list)[0]) => b.last - a.last,
    name: (a: (typeof list)[0], b: (typeof list)[0]) => a.p.name.localeCompare(b.p.name, 'ko'),
    received: (a: (typeof list)[0], b: (typeof list)[0]) => b.t.received - a.t.received,
    diff: (a: (typeof list)[0], b: (typeof list)[0]) => Math.abs(b.t.received - b.t.given) - Math.abs(a.t.received - a.t.given),
  }[sort.value]
  return list.sort(by)
})
</script>

<template>
  <div class="page" :class="{ selecting }">
    <input v-model="q" class="field" type="search" placeholder="이름·소속 검색" aria-label="이름 검색" />
    <div class="chips scroll filters">
      <button class="chip" :aria-pressed="relation === 'all'" @click="relation = 'all'">전체</button>
      <button v-for="r in RELATIONS" :key="r.value" class="chip" :aria-pressed="relation === r.value" @click="relation = r.value">{{ r.label }}</button>
    </div>
    <div class="between sortbar">
      <span class="muted small">총 {{ rows.length }}명</span>
      <button v-if="!selecting && rows.length" class="chip sel-btn" @click="startSelect">선택</button>
      <button v-else-if="selecting" class="chip sel-btn" @click="toggleAllShown">{{ allShownPicked ? '선택 해제' : '모두 선택' }}</button>
      <select v-model="sort" class="sort" aria-label="정렬">
        <option value="recent">최근 기록순</option>
        <option value="name">이름순</option>
        <option value="received">받은 금액순</option>
        <option value="diff">차이 큰 순</option>
      </select>
    </div>

    <div v-if="rows.length" class="card flush">
      <ul class="list">
        <li v-for="x in rows" :key="x.p.id">
          <label v-if="selecting" class="list-row pick">
            <input type="checkbox" :checked="picked.has(x.p.id)" @change="togglePick(x.p.id)" />
            <span class="grow"><strong>{{ x.p.name }}</strong><span class="muted small rel">{{ relationLabel(x.p.relation) }}<template v-if="x.p.group"> · {{ x.p.group }}</template></span></span>
          </label>
          <RouterLink v-else :to="`/people/${x.p.id}`" class="list-row">
            <span class="grow">
              <strong>{{ x.p.name }}</strong>
              <span class="muted small rel">{{ relationLabel(x.p.relation) }}<template v-if="x.p.group"> · {{ x.p.group }}</template></span><br />
              <span class="small">
                <span class="received">받음 {{ formatShort(x.t.received) }}</span> ·
                <span class="given">보냄 {{ formatShort(x.t.given) }}</span>
              </span>
            </span>
            <span v-if="x.diff" class="muted small diff">{{ x.diff }}</span>
          </RouterLink>
        </li>
      </ul>
    </div>
    <div v-else class="card empty">
      <p class="muted">{{ q || relation !== 'all' ? '찾는 사람이 없어요.' : '아직 등록한 사람이 없어요.' }}</p>
    </div>

    <div v-if="selecting" class="relbar">
      <div class="between">
        <strong class="small">{{ picked.size }}명 선택 · 관계를</strong>
        <button class="chip" @click="stopSelect">취소</button>
      </div>
      <div class="chips">
        <button v-for="r in RELATIONS" :key="r.value" class="chip" :aria-pressed="newRelation === r.value" @click="newRelation = r.value">{{ r.label }}</button>
      </div>
      <button class="btn" :disabled="!picked.size || saving" @click="applyRelation">
        {{ picked.size ? `${picked.size}명을 "${relationLabel(newRelation)}"(으)로 바꾸기` : '바꿀 사람을 골라 주세요' }}
      </button>
      <button class="btn outline" :disabled="!picked.size || saving" @click="removePicked">
        {{ picked.size ? `${picked.size}명 삭제` : '선택한 사람 삭제' }}
      </button>
    </div>

    <div v-if="!selecting" class="btn-row add">
      <RouterLink to="/people/new" class="btn outline">사람 추가</RouterLink>
      <RouterLink to="/contacts" class="btn outline">📇 연락처에서 불러오기</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.filters { margin: 12px 0 8px; }
.sortbar { margin: 4px 2px 10px; }
.selecting { padding-bottom: calc(var(--tab-h) + 290px + env(safe-area-inset-bottom)); }
.sel-btn { padding: 5px 12px; font-size: 0.85rem; }
.pick { cursor: pointer; }
.pick input { width: 20px; height: 20px; flex: none; }
.relbar {
  position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(var(--tab-h) + env(safe-area-inset-bottom));
  width: 100%; max-width: 480px; z-index: 25; background: var(--surface); border-top: 1px solid var(--line);
  padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 -4px 14px rgb(0 0 0 / 0.08);
}
.sort { border: 0; background: none; color: var(--text-2); font-size: 0.88rem; padding: 4px; }
.diff { text-align: right; white-space: nowrap; }
.add { margin-top: 16px; }
</style>
