<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MoodChart from '../components/MoodChart.vue'
import { entriesBetween, getSetting, setSetting } from '../lib/db'
import { addDays, formatDot, formatShort, todayKey } from '../lib/date'
import { MOODS, type Entry } from '../lib/mood'
import { summarize } from '../lib/summary'
import { isNativeApp } from '../lib/platform'

/** S-05 진료용 리포트. 진료실에서 보여주거나 PDF로 저장. 서버를 거치지 않는다. */
const route = useRoute()
const today = todayKey()
const days = computed(() => {
  const n = Number(route.query.days)
  return [7, 14, 28].includes(n) ? n : 14
})
const from = computed(() => addDays(today, -(days.value - 1)))

const entries = ref<Entry[]>([])
const note = ref('')
const includeMemo = ref(true)
const ready = ref(false)
const summary = computed(() => summarize(entries.value, from.value, today))

onMounted(async () => {
  entries.value = await entriesBetween(from.value, today)
  note.value = await getSetting('visitNote', '')
  includeMemo.value = await getSetting('reportIncludeMemo', true)
  ready.value = true
})
watch(includeMemo, (v) => ready.value && setSetting('reportIncludeMemo', v))

const printPdf = () => window.print()
</script>

<template>
  <div class="page report-page">
    <div class="toolbar no-print">
      <label class="toggle">
        <input v-model="includeMemo" type="checkbox" />
        메모 포함
      </label>
      <button v-if="!isNativeApp" class="btn pdf" @click="printPdf">PDF 저장</button>
    </div>
    <p v-if="isNativeApp" class="muted no-print hint">앱에서는 PDF 저장을 준비 중이에요. 이 화면을 그대로 보여주세요.</p>
    <p v-else class="muted no-print hint">인쇄 창에서 “PDF로 저장”을 고르세요.</p>

    <article v-if="ready" class="report card">
      <header>
        <h1>기분 기록 요약</h1>
        <p class="range">{{ formatDot(summary.from) }} ~ {{ formatDot(summary.to) }} ({{ summary.totalDays }}일)</p>
      </header>

      <section>
        <h2>■ 기분 분포 <span class="muted small">(날짜 기준)</span></h2>
        <p class="dist">
          <span v-for="(m, i) in MOODS" :key="m.value">{{ m.label }} {{ summary.distribution[i] }}</span>
        </p>
        <p class="muted">기록한 날 {{ summary.recordedDays }}일</p>
      </section>

      <section>
        <h2>■ 날짜별 흐름</h2>
        <MoodChart :daily="summary.daily" />
        <p class="muted small">위쪽일수록 좋음, 아래쪽일수록 힘듦. 점이 없는 날은 기록이 없는 날이에요.</p>
      </section>

      <section v-if="summary.topTags.length">
        <h2>■ 자주 남긴 태그</h2>
        <p>{{ summary.topTags.map((t) => `${t.tag} ${t.count}`).join(' · ') }}</p>
      </section>

      <section v-if="includeMemo && summary.memos.length">
        <h2>■ 메모 <span class="muted small">(최근순, 최대 5개)</span></h2>
        <ul class="memos">
          <li v-for="m in summary.memos" :key="m.date + m.time"><span class="muted">{{ formatShort(m.date) }}</span> {{ m.memo }}</li>
        </ul>
      </section>

      <section v-if="note.trim()">
        <h2>■ 하고 싶은 말</h2>
        <p class="note">{{ note.trim() }}</p>
      </section>

      <footer class="muted small">본인이 직접 기록한 내용입니다. 의학적 평가가 아닙니다.</footer>
    </article>
  </div>
</template>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; }
.toggle { display: flex; align-items: center; gap: 6px; flex: 1; }
.toggle input { width: 20px; height: 20px; accent-color: var(--accent); }
.pdf { width: auto; padding: 10px 18px; }
.hint { margin: 6px 0 12px; }

/* 상대에게 화면을 보여주는 상황이라 본문보다 크게 (screens.md S-05) */
.report { font-size: 1.05rem; }
.report header { border-bottom: 2px solid var(--text); padding-bottom: 10px; margin-bottom: 14px; }
.report h1 { font-size: 1.4rem; }
.range { margin: 0; font-variant-numeric: tabular-nums; }
.report section { margin-bottom: 18px; }
.report h2 { font-size: 1.02rem; margin-bottom: 6px; }
.dist { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 0 0 4px; }
.small { font-size: 0.82rem; font-weight: 400; }
.memos { margin: 0; padding-left: 0; list-style: none; }
.memos li { padding: 3px 0; }
.note { white-space: pre-wrap; margin: 0; }
.report footer { border-top: 1px solid var(--line); padding-top: 10px; }

@media print {
  .no-print { display: none !important; }
  .page { padding: 0; }
  .report { border: 0; padding: 0; font-size: 12pt; color: #000; background: #fff; }
  .report :deep(svg) { max-width: 130mm; }
}
</style>

<style>
@media print {
  @page { size: A4; margin: 16mm; }
  html, body { background: #fff !important; }
  #app { max-width: none; }
}
</style>
