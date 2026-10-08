<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { ledger } from '../lib/store'
import { loadAll, replaceAll, setSetting, getSetting } from '../lib/db'
import { matchPeople, mergeData, openBackup, previewOf, readBackupFile, type BackupFile, type NameConflict } from '../lib/backup'
import { type ImportIssue, type ImportResult } from '../lib/importData'
import { isSheetFile, readSheetFile } from '../lib/sheetFile'
import { takePendingImport } from '../lib/pendingImport'
import { WrongPasswordError } from '../lib/crypto'
import { confirmAsk } from '../lib/dialog'
import { formatDot } from '../lib/date'
import { isNativeApp } from '../lib/platform'
import { relationLabel, type LedgerData } from '../lib/types'
import { showToast } from '../lib/toast'

/** S-12 가져오기·복원: 마음장부 백업(.json) / 엑셀(.xlsx) / CSV */
const fileInput = ref<HTMLInputElement | null>(null)
const file = shallowRef<BackupFile | null>(null)
const fileName = ref('')
const password = ref('')
// shallowRef: 가져온 데이터를 Vue 반응형(Proxy)으로 감싸지 않아야 IndexedDB에 그대로 저장된다
const incoming = shallowRef<LedgerData | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)
const mode = ref<'merge' | 'replace'>('merge')
const conflicts = ref<NameConflict[]>([])
const autoSame = ref<Record<string, string>>({})
const sheetFile = ref(false)
const issues = ref<ImportIssue[]>([])
const unknownColumns = ref<string[]>([])
const sameAs = ref<Record<string, 'same' | 'diff' | undefined>>({})
const done = ref<string | null>(null)
const canUndo = ref(false)

const preview = computed(() => (incoming.value ? previewOf(incoming.value) : null))
const currentCount = computed(() => ledger.value.records.length + ledger.value.events.length)
const merged = computed(() => {
  if (!incoming.value) return null
  const map: Record<string, string> = { ...autoSame.value }
  for (const c of conflicts.value) if (sameAs.value[c.incoming.id] === 'same') map[c.incoming.id] = c.existing.id
  return mergeData(ledger.value, incoming.value, map)
})
const unanswered = computed(() => mode.value === 'merge' && conflicts.value.some((c) => !sameAs.value[c.incoming.id]))

function reset() {
  file.value = null
  incoming.value = null
  password.value = ''
  error.value = null
  conflicts.value = []
  autoSame.value = {}
  sameAs.value = {}
  sheetFile.value = false
  issues.value = []
  unknownColumns.value = []
  done.value = null
}

function setIncoming(d: LedgerData) {
  incoming.value = d
  const m = matchPeople(ledger.value, d)
  autoSame.value = m.sameAs
  conflicts.value = m.conflicts
  mode.value = 'merge'
}

/** 같은 사람인지 한꺼번에 답하기 */
function answerAll(v: 'same' | 'diff') {
  sameAs.value = Object.fromEntries(conflicts.value.map((c) => [c.incoming.id, v]))
}

function useSheetResult(name: string, res: ImportResult) {
  fileName.value = name
  sheetFile.value = true
  issues.value = res.issues
  unknownColumns.value = res.unknownColumns
  setIncoming(res.data)
}

// 일괄 등록 화면에서 넘어온 파일 (이미 읽은 결과)
onMounted(() => {
  const p = takePendingImport()
  if (p) useSheetResult(p.fileName, p.result)
})

async function onFile(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (fileInput.value) fileInput.value.value = ''
  if (!f) return
  reset()
  fileName.value = f.name
  if (isSheetFile(f.name)) {
    busy.value = true
    try {
      useSheetResult(f.name, await readSheetFile(f))
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      busy.value = false
    }
    return
  }
  try {
    const parsed = readBackupFile(await f.text())
    file.value = parsed
    if (!parsed.encrypted) await open()
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function open() {
  if (!file.value) return
  busy.value = true
  error.value = null
  try {
    setIncoming(await openBackup(file.value, password.value))
  } catch (e) {
    error.value = e instanceof WrongPasswordError ? '비밀번호가 맞지 않아요.' : (e as Error).message
  } finally {
    busy.value = false
  }
}

async function run() {
  if (!incoming.value || !merged.value) return
  if (mode.value === 'replace' && currentCount.value > 0) {
    const ok = await confirmAsk('덮어쓸까요?', '지금 휴대폰의 기록을 모두 지우고 백업 내용으로 바꿔요.\n바로 다음에 한 번 되돌릴 수 있어요.', '덮어쓰기')
    if (!ok) return
  }
  busy.value = true
  try {
    // 덮어쓰기 전에 현재 데이터를 임시 보관 → [되돌리기] 1회 (tech-stack.md 5-2)
    if (mode.value === 'replace' && currentCount.value > 0) {
      await setSetting('undoSnapshot', await loadAll())
      canUndo.value = true
    }
    if (mode.value === 'replace' || currentCount.value === 0) {
      await replaceAll(incoming.value)
      done.value = `사람 ${incoming.value.people.length}명, 기록 ${incoming.value.records.length}건을 가져왔어요.`
    } else {
      await replaceAll(merged.value.result)
      const a = merged.value.added
      done.value = `사람 ${a.people}명, 행사 ${a.events}개, 기록 ${a.records}건을 합쳤어요.` + (merged.value.skippedRecords ? ` (중복 ${merged.value.skippedRecords}건 제외)` : '')
    }
    incoming.value = null
    file.value = null
    sheetFile.value = false
  } catch (e) {
    error.value = `가져오지 못했어요. (${(e as Error).message})`
  } finally {
    busy.value = false
  }
}

async function undo() {
  const snap = await getSetting<LedgerData | null>('undoSnapshot', null)
  if (!snap) return
  await replaceAll(snap)
  await setSetting('undoSnapshot', null)
  canUndo.value = false
  done.value = null
  showToast('덮어쓰기 전으로 되돌렸어요')
}
</script>

<template>
  <div class="page no-tab">
    <div v-if="done" class="card ok">
      <p><strong>✓ {{ done }}</strong></p>
      <div class="btn-row">
        <button v-if="canUndo" class="btn secondary" @click="undo">되돌리기</button>
        <RouterLink to="/" class="btn">홈으로</RouterLink>
      </div>
    </div>

    <template v-else-if="!file && !incoming">
      <div class="card">
        <h2>가져올 파일을 골라 주세요</h2>
        <ul class="muted small kinds">
          <li><strong>마음장부 백업</strong> (.json) — 다른 휴대폰이나 예전 백업</li>
          <li><strong>엑셀</strong> (.xlsx) · <strong>CSV</strong> — 내보낸 엑셀을 고친 파일이나 직접 정리한 명단</li>
        </ul>
        <button class="btn pick" :disabled="busy" @click="fileInput?.click()">{{ busy ? '읽는 중…' : '파일 선택' }}</button>
        <!-- 안드로이드 파일 선택기는 .json을 MIME으로 못 알아보는 경우가 있어 앱에서는 제한하지 않는다 -->
        <input ref="fileInput" type="file" hidden :accept="isNativeApp ? undefined : '.json,.xlsx,.csv,application/json,text/csv'" @change="onFile" />
      </div>
      <div class="card tpl">
        <p class="small"><strong>엑셀로 직접 정리하려면</strong><br /><span class="muted">날짜, 행사, 이름, 금액 열만 있으면 돼요. "축의금", "성명", "일자" 같은 열 이름도 알아봐요.</span></p>
        <RouterLink to="/bulk" class="btn sm secondary">엑셀·CSV 양식 받기 · 작성 방법</RouterLink>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </template>

    <template v-else-if="file && file.encrypted && !incoming">
      <div class="card">
        <h2>비밀번호가 걸린 백업이에요</h2>
        <p class="muted small">{{ fileName }}</p>
        <input v-model="password" class="field" type="password" placeholder="백업할 때 정한 비밀번호" aria-label="비밀번호" @keyup.enter="open" />
        <button class="btn pick" :disabled="busy || !password" @click="open">{{ busy ? '확인 중…' : '열기' }}</button>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </div>
      <button class="btn outline back" @click="reset">다른 파일 고르기</button>
    </template>

    <template v-else-if="incoming && preview">
      <div class="card">
        <h2>{{ sheetFile ? '엑셀·CSV 파일' : '마음장부 백업' }}</h2>
        <p class="muted small">{{ fileName }}</p>
        <p class="big">사람 {{ preview.people }} · 행사 {{ preview.events }} · 기록 {{ preview.records }}건</p>
        <p v-if="preview.from" class="muted small">{{ formatDot(preview.from) }} ~ {{ formatDot(preview.to!) }}</p>
        <p v-if="Object.keys(autoSame).length" class="muted small">이미 있는 사람 {{ Object.keys(autoSame).length }}명은 이름·소속이 같아 같은 사람으로 연결해요.</p>
      </div>

      <div v-if="issues.length || unknownColumns.length" class="card warnbox">
        <p v-if="issues.length"><strong>{{ issues.length }}줄은 읽을 수 없어 빼고 가져와요.</strong></p>
        <ul v-if="issues.length" class="small issues">
          <li v-for="x in issues.slice(0, 5)" :key="x.line">{{ x.line }}번째 줄: {{ x.reason }}</li>
          <li v-if="issues.length > 5">외 {{ issues.length - 5 }}줄</li>
        </ul>
        <p v-if="unknownColumns.length" class="small">알아보지 못한 열은 가져오지 않아요: {{ unknownColumns.join(', ') }}</p>
      </div>

      <template v-if="currentCount > 0">
        <p class="now muted">지금 휴대폰에는 기록 {{ ledger.records.length }}건이 있어요.</p>
        <div class="stack">
          <label class="card row opt">
            <input v-model="mode" type="radio" value="merge" />
            <span><strong>합치기 (추천)</strong><br /><span class="muted small">중복 {{ merged?.skippedRecords ?? 0 }}건은 건너뛰어요</span></span>
          </label>
          <label class="card row opt">
            <input v-model="mode" type="radio" value="replace" />
            <span><strong>덮어쓰기</strong><br /><span class="muted small">지금 기록을 지우고 백업으로 바꿔요</span></span>
          </label>
        </div>

        <template v-if="mode === 'merge' && conflicts.length">
          <div class="between">
            <h2 class="section-title">같은 사람인지 확인해 주세요 ({{ conflicts.length }})</h2>
            <span v-if="conflicts.length > 1" class="row">
              <button class="chip" @click="answerAll('same')">모두 같은 사람</button>
              <button class="chip" @click="answerAll('diff')">모두 다른 사람</button>
            </span>
          </div>
          <div class="card flush">
            <ul class="list">
              <li v-for="c in conflicts" :key="c.incoming.id" class="conflict">
                <p>
                  <strong>{{ c.existing.name }}</strong> <span class="muted small">({{ relationLabel(c.existing.relation) }}{{ c.existing.group ? ` · ${c.existing.group}` : '' }})</span>
                  ↔ <strong>{{ c.incoming.name }}</strong> <span class="muted small">({{ relationLabel(c.incoming.relation) }}{{ c.incoming.group ? ` · ${c.incoming.group}` : '' }})</span>
                </p>
                <div class="chips">
                  <button class="chip" :aria-pressed="sameAs[c.incoming.id] === 'same'" @click="sameAs = { ...sameAs, [c.incoming.id]: 'same' }">같은 사람</button>
                  <button class="chip" :aria-pressed="sameAs[c.incoming.id] === 'diff'" @click="sameAs = { ...sameAs, [c.incoming.id]: 'diff' }">다른 사람</button>
                </div>
              </li>
            </ul>
          </div>
        </template>
      </template>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="btn run" :disabled="busy || unanswered" @click="run">
        {{ unanswered ? '같은 사람인지 모두 골라 주세요' : '가져오기' }}
      </button>
      <button class="btn outline back" @click="reset">취소</button>
    </template>
  </div>
</template>

<style scoped>
.card h2 { margin-bottom: 4px; }
.card p { margin: 0 0 6px; }
.pick { margin-top: 12px; }
.error { color: var(--warn); background: var(--warn-soft); padding: 10px 12px; border-radius: 10px; margin-top: 12px; }
.big { font-weight: 800; font-size: 1.05rem; margin-top: 8px !important; }
.now { margin: 16px 4px 10px; }
.opt { cursor: pointer; align-items: flex-start; }
.opt input { width: 20px; height: 20px; margin-top: 3px; }
.conflict { padding: 12px 16px; }
.conflict p { margin: 0 0 8px; }
.run { margin-top: 18px; }
.back { margin-top: 10px; }
.ok { background: var(--received-soft); border-color: transparent; }
.kinds { padding-left: 18px; margin: 8px 0 0; }
.tpl { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.tpl p { margin: 0; }
.warnbox { margin-top: 12px; background: var(--warn-soft); border-color: transparent; }
.issues { margin: 4px 0 6px; padding-left: 18px; }
</style>
