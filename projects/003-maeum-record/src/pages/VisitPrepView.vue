<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import SummaryBlock from '../components/SummaryBlock.vue'
import { entriesBetween, getSetting, setSetting } from '../lib/db'
import { addDays, todayKey } from '../lib/date'
import type { Entry } from '../lib/mood'
import { summarize } from '../lib/summary'

/** S-04 첫 진료 준비하기 */
const today = todayKey()
const PERIODS = [
  { days: 7, label: '최근 1주' },
  { days: 14, label: '최근 2주' },
  { days: 28, label: '최근 4주' },
]
const periodDays = ref(14)
const from = computed(() => addDays(today, -(periodDays.value - 1)))

const entries = ref<Entry[]>([])
const note = ref('')
const loaded = ref(false)
const summary = computed(() => summarize(entries.value, from.value, today))

const PROMPTS = ['언제부터 이랬는지', '잠, 식사, 일상에 어떤 변화가 있는지', '가장 힘든 순간은 언제인지', '궁금한 점 (약, 비용, 기간 등)']

async function load() {
  entries.value = await entriesBetween(from.value, today)
}

function addPrompt(p: string) {
  note.value = note.value.trim() ? `${note.value.trimEnd()}\n${p}: ` : `${p}: `
}

let saveTimer: ReturnType<typeof setTimeout> | undefined
watch(note, (v) => {
  if (!loaded.value) return
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => setSetting('visitNote', v), 400)
})
watch(periodDays, load)

onMounted(async () => {
  note.value = await getSetting('visitNote', '')
  await load()
  loaded.value = true
})
</script>

<template>
  <div class="page stack">
    <h1>진료·상담 준비하기</h1>

    <label class="period">
      <span class="muted">기간</span>
      <select v-model.number="periodDays" class="field">
        <option v-for="p in PERIODS" :key="p.days" :value="p.days">{{ p.label }}</option>
      </select>
    </label>

    <section class="card">
      <SummaryBlock v-if="summary.recordedDays" :summary="summary" />
      <p v-else class="muted empty">기록이 없어도 괜찮아요. 하고 싶은 말만 정리해서 가져갈 수 있어요.</p>
    </section>

    <section class="stack">
      <h2>진료 때 하고 싶은 말</h2>
      <textarea v-model="note" class="field" rows="5" placeholder="생각나는 대로 적어두세요. 자동으로 저장돼요." />
      <details class="card prompts">
        <summary>무슨 말을 할지 모르겠다면</summary>
        <ul class="list">
          <li v-for="p in PROMPTS" :key="p">
            <button class="list-row" @click="addPrompt(p)">
              <span>{{ p }}</span><span class="muted">+ 추가</span>
            </button>
          </li>
        </ul>
      </details>
    </section>

    <RouterLink class="btn" :to="{ name: 'report', query: { days: periodDays } }">리포트 보기</RouterLink>
  </div>
</template>

<style scoped>
.period { display: flex; align-items: center; gap: 12px; }
.period .field { flex: 1; }
.empty { margin: 0; }
.prompts { padding: 0; }
.prompts summary { padding: 14px 16px; cursor: pointer; color: var(--text-2); }
.prompts .list-row { padding: 12px 16px; font-size: 0.95rem; }
</style>
