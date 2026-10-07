<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger } from '../lib/store'
import { diffShort, totalsByPerson } from '../lib/ledger'
import { formatShort } from '../lib/money'
import { RELATIONS, relationLabel, type Relation } from '../lib/types'

/** S-03 사람 목록 */
const q = ref('')
const relation = ref<Relation | 'all'>('all')
const sort = ref<'recent' | 'name' | 'received' | 'diff'>('recent')

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
  <div class="page">
    <input v-model="q" class="field" type="search" placeholder="이름·소속 검색" aria-label="이름 검색" />
    <div class="chips scroll filters">
      <button class="chip" :aria-pressed="relation === 'all'" @click="relation = 'all'">전체</button>
      <button v-for="r in RELATIONS" :key="r.value" class="chip" :aria-pressed="relation === r.value" @click="relation = r.value">{{ r.label }}</button>
    </div>
    <div class="between sortbar">
      <span class="muted small">총 {{ rows.length }}명</span>
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
          <RouterLink :to="`/people/${x.p.id}`" class="list-row">
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

    <RouterLink to="/people/new" class="btn outline add">사람 추가</RouterLink>
  </div>
</template>

<style scoped>
.filters { margin: 12px 0 8px; }
.sortbar { margin: 4px 2px 10px; }
.sort { border: 0; background: none; color: var(--text-2); font-size: 0.88rem; padding: 4px; }
.diff { text-align: right; white-space: nowrap; }
.add { margin-top: 16px; }
</style>
