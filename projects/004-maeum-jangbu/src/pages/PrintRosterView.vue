<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ledger, eventsById } from '../lib/store'
import { rosters } from '../lib/sheet'
import { formatDot } from '../lib/date'
import { formatShort } from '../lib/money'
import { printPage } from '../lib/print'
import { showToast } from '../lib/toast'
import { ask } from '../lib/dialog'

/** PDF 답례 명단 (A4). 인쇄 화면에서 "PDF로 저장" — 서버를 거치지 않는다 */
const route = useRoute()
const id = String(route.params.id)
const event = computed(() => eventsById.value.get(id))
const onlyUnthanked = ref(false)
const roster = computed(() => {
  const r = rosters({ ...ledger.value, events: ledger.value.events.filter((e) => e.id === id) })[0]
  if (!r || !onlyUnthanked.value) return r
  const rows = r.rows.filter((x) => x[7] !== '완료').map((x, i) => [i + 1, ...x.slice(1)])
  return { ...r, rows, total: rows.reduce((s, x) => s + Number(x[4]), 0) }
})

async function print() {
  // PDF는 비밀번호를 걸 수 없어 매번 안내 (screens.md S-11)
  const ok = await ask('PDF로 저장할까요?', '이 명단에는 이름과 금액이 그대로 들어 있어요.\n카카오톡·이메일로 보내면 파일을 받은 사람도 볼 수 있어요.', [
    { label: '취소', value: false },
    { label: '계속', value: true, primary: true },
  ])
  if (!ok) return
  try {
    await printPage(`${event.value?.title ?? '마음장부'} 명단`)
  } catch (e) {
    showToast(`인쇄 화면을 열지 못했어요 (${(e as Error).message})`, 3000)
  }
}
</script>

<template>
  <div class="page no-tab sheet">
    <div class="no-print controls">
      <label class="row small"><input v-model="onlyUnthanked" type="checkbox" /> 감사 인사 안 한 사람만</label>
      <button class="btn" @click="print">PDF로 저장 · 인쇄</button>
      <p class="muted small">인쇄 화면에서 프린터 대신 "PDF로 저장"을 고르세요.</p>
    </div>

    <template v-if="event">
      <h1>{{ event.title }} 명단</h1>
      <p class="muted">{{ formatDot(event.date) }}<template v-if="event.place"> · {{ event.place }}</template></p>
      <template v-if="roster">
        <p class="sum">{{ roster.rows.length }}명 · 합계 {{ formatShort(roster.total) }}</p>
        <table>
          <thead>
            <tr><th>번호</th><th>이름</th><th>관계</th><th>소속</th><th class="num">금액</th><th>방식</th><th>감사 인사</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in roster.rows" :key="String(r[0]) + r[1]">
              <td>{{ r[0] }}</td><td><strong>{{ r[1] }}</strong></td><td>{{ r[2] }}</td><td>{{ r[3] }}</td>
              <td class="num">{{ r[4] ? formatShort(Number(r[4])) : '' }}</td><td>{{ r[5] }}</td>
              <td class="check">{{ r[7] === '완료' ? '☑' : '☐' }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <p v-else class="muted">명단이 없어요.</p>
      <p class="foot muted small">마음장부에서 만든 명단입니다.</p>
    </template>
  </div>
</template>

<style scoped>
.controls { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px dashed var(--line); }
.sum { font-weight: 800; margin: 8px 0 10px; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; background: var(--surface); }
th, td { border: 1px solid var(--line); padding: 6px 6px; text-align: left; }
th { background: var(--accent-soft); white-space: nowrap; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.check { text-align: center; }
.foot { margin-top: 14px; }

@media print {
  @page { size: A4; margin: 14mm; }
  .no-print { display: none !important; }
  .sheet { padding: 0 !important; }
  :global(html), :global(body) { background: #fff !important; color: #000 !important; }
  :global(#app) { max-width: none; }
  table { font-size: 10pt; background: #fff; }
  th, td { border-color: #999; color: #000; }
  th { background: #eee !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  tr { break-inside: avoid; }
  thead { display: table-header-group; }
}
</style>
