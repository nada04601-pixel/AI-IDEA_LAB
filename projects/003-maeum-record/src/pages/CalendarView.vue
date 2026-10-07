<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EntryForm from '../components/EntryForm.vue'
import { addEntry, deleteEntry, entriesBetween, updateEntry } from '../lib/db'
import { WEEKDAYS, formatLong, formatTime, fromKey, monthCells, nowTime, todayKey, toKey } from '../lib/date'
import { moodInfo, type Entry, type Mood } from '../lib/mood'
import { dayMood, groupByDate } from '../lib/summary'
import { showToast, toastText } from '../lib/toast'

/** S-03 기록 달력 */
const today = todayKey()
const cursor = ref(fromKey(today))
cursor.value.setDate(1)

const year = computed(() => cursor.value.getFullYear())
const month0 = computed(() => cursor.value.getMonth())
const cells = computed(() => monthCells(year.value, month0.value))
const byDate = ref(new Map<string, Entry[]>())

const selected = ref<string | null>(null)
const mode = ref<'view' | 'add' | { edit: Entry }>('view')

async function load() {
  const first = toKey(new Date(year.value, month0.value, 1))
  const last = toKey(new Date(year.value, month0.value + 1, 0))
  byDate.value = groupByDate(await entriesBetween(first, last))
}

function move(n: number) {
  cursor.value = new Date(year.value, month0.value + n, 1)
  load()
}

const canGoNext = computed(() => toKey(new Date(year.value, month0.value + 1, 1)) <= today)
const selectedEntries = computed(() => (selected.value ? byDate.value.get(selected.value) ?? [] : []))

function open(date: string | null) {
  if (!date || date > today) return
  selected.value = date
  mode.value = 'view'
}

async function add(v: { mood: Mood; memo: string; tags: string[] }) {
  if (!selected.value) return
  // 지난 날짜에 추가하면 시각은 현재 시각으로 둔다 (프로토타입)
  await addEntry({ ...v, date: selected.value, time: nowTime() })
  mode.value = 'view'
  showToast('기록했어요')
  await load()
}

async function edit(id: string, v: { mood: Mood; memo: string; tags: string[] }) {
  await updateEntry(id, { mood: v.mood, memo: v.memo.trim(), tags: v.tags })
  mode.value = 'view'
  showToast('수정했어요')
  await load()
}

async function remove(e: Entry) {
  if (!confirm('이 기록을 삭제할까요? 되돌릴 수 없어요.')) return
  await deleteEntry(e.id)
  await load()
}

const editing = computed(() => (typeof mode.value === 'object' ? mode.value.edit : null))

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="month-nav">
      <button class="nav" aria-label="이전 달" @click="move(-1)">◀</button>
      <h1>{{ year }}년 {{ month0 + 1 }}월</h1>
      <button class="nav" aria-label="다음 달" :disabled="!canGoNext" @click="move(1)">▶</button>
    </div>

    <div class="grid card">
      <span v-for="w in WEEKDAYS" :key="w" class="wd">{{ w }}</span>
      <button
        v-for="(d, i) in cells"
        :key="d ?? `blank-${i}`"
        class="cell"
        :class="{ today: d === today, future: d && d > today, blank: !d }"
        :disabled="!d || d > today"
        @click="open(d)"
      >
        <template v-if="d">
          <span class="num">{{ Number(d.slice(8)) }}</span>
          <span
            v-if="byDate.get(d)?.length"
            class="dot"
            :style="{ background: moodInfo(dayMood(byDate.get(d)!)!).color }"
            :title="moodInfo(dayMood(byDate.get(d)!)!).label"
          />
        </template>
      </button>
    </div>
    <p class="muted legend">점 색은 그날 기록의 평균 기분이에요.</p>

    <!-- 날짜별 기록 시트 -->
    <div v-if="selected" class="backdrop" @click.self="selected = null">
      <section class="sheet" role="dialog" :aria-label="formatLong(selected)">
        <div class="sheet-head">
          <h2>{{ formatLong(selected) }}</h2>
          <button class="nav" aria-label="닫기" @click="selected = null">✕</button>
        </div>

        <template v-if="mode === 'view'">
          <p v-if="!selectedEntries.length" class="muted">이 날짜에는 기록이 없어요.</p>
          <ul class="list">
            <li v-for="e in selectedEntries" :key="e.id" class="entry">
              <div class="entry-main">
                <span class="muted">{{ formatTime(e.time) }}</span>
                <span>{{ moodInfo(e.mood).emoji }} {{ moodInfo(e.mood).label }}</span>
              </div>
              <p v-if="e.memo" class="memo">“{{ e.memo }}”</p>
              <p v-if="e.tags.length" class="muted tags">{{ e.tags.map((t) => `#${t}`).join(' ') }}</p>
              <div class="actions">
                <button class="chip" @click="mode = { edit: e }">수정</button>
                <button class="chip" @click="remove(e)">삭제</button>
              </div>
            </li>
          </ul>
          <button class="btn secondary" @click="mode = 'add'">+ 이 날짜에 기록 추가</button>
        </template>

        <EntryForm v-else-if="mode === 'add'" question="이 날 기분은 어땠어요?" @submit="add" />
        <EntryForm
          v-else-if="editing"
          :initial="{ mood: editing.mood, memo: editing.memo, tags: editing.tags }"
          submit-label="저장"
          question="기록 수정"
          @submit="(v) => edit(editing!.id, v)"
          @cancel="mode = 'view'"
        />
      </section>
    </div>

    <div v-if="toastText" class="toast" role="status">{{ toastText }}</div>
  </div>
</template>

<style scoped>
.month-nav { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.month-nav h1 { font-size: 1.15rem; margin: 0; }
.nav { width: 40px; height: 40px; border: 0; background: none; border-radius: 10px; font-size: 1rem; }
.nav:disabled { opacity: 0.3; }
.grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; padding: 10px 8px; }
.wd { text-align: center; font-size: 0.78rem; color: var(--text-2); padding-bottom: 6px; }
.cell {
  aspect-ratio: 1 / 1.1; display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
  gap: 4px; padding-top: 6px; border: 0; background: none; border-radius: 10px;
}
.cell.blank { visibility: hidden; }
.cell.future { color: var(--text-2); opacity: 0.4; }
.cell.today .num { font-weight: 800; text-decoration: underline; text-underline-offset: 3px; }
.num { font-size: 0.9rem; }
.dot { width: 14px; height: 14px; border-radius: 50%; }
.legend { margin-top: 10px; }

.backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.35); z-index: 30; display: flex; align-items: flex-end; justify-content: center; }
.sheet {
  width: 100%; max-width: 480px; max-height: 85dvh; overflow-y: auto;
  background: var(--bg); border-radius: 20px 20px 0 0; padding: 16px 16px calc(24px + env(safe-area-inset-bottom));
}
.sheet-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.sheet-head h2 { margin: 0; }
.entry { padding: 12px 0; border-bottom: 1px solid var(--line); }
.entry-main { display: flex; gap: 12px; }
.memo { margin: 6px 0 0; }
.tags { margin: 4px 0 0; }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.list + .btn { margin-top: 16px; }
</style>
