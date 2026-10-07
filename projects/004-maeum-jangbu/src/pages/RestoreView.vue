<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger } from '../lib/store'
import { loadAll, replaceAll, setSetting, getSetting } from '../lib/db'
import { findNameConflicts, mergeData, openBackup, previewOf, readBackupFile, type BackupFile, type NameConflict } from '../lib/backup'
import { WrongPasswordError } from '../lib/crypto'
import { confirmAsk } from '../lib/dialog'
import { formatDot } from '../lib/date'
import { isNativeApp } from '../lib/platform'
import { relationLabel, type LedgerData } from '../lib/types'
import { showToast } from '../lib/toast'

/** S-12 가져오기·복원 */
const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<BackupFile | null>(null)
const fileName = ref('')
const password = ref('')
const incoming = ref<LedgerData | null>(null)
const error = ref<string | null>(null)
const busy = ref(false)
const mode = ref<'merge' | 'replace'>('merge')
const conflicts = ref<NameConflict[]>([])
const sameAs = ref<Record<string, 'same' | 'diff' | undefined>>({})
const done = ref<string | null>(null)
const canUndo = ref(false)

const preview = computed(() => (incoming.value ? previewOf(incoming.value) : null))
const currentCount = computed(() => ledger.value.records.length + ledger.value.events.length)
const merged = computed(() => {
  if (!incoming.value) return null
  const map: Record<string, string> = {}
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
  sameAs.value = {}
  done.value = null
}

async function onFile(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (fileInput.value) fileInput.value.value = ''
  if (!f) return
  reset()
  fileName.value = f.name
  if (/\.(xlsx|xls|csv)$/i.test(f.name)) {
    error.value = '엑셀·CSV 가져오기는 다음 업데이트에서 제공해요. 지금은 마음장부 백업 파일(.json)만 가져올 수 있어요.'
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
    incoming.value = await openBackup(file.value, password.value)
    conflicts.value = findNameConflicts(ledger.value, incoming.value)
    mode.value = 'merge'
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

    <template v-else-if="!file">
      <div class="card">
        <h2>가져올 파일을 골라 주세요</h2>
        <p class="muted small">마음장부 백업 파일(.json)을 가져올 수 있어요.<br />엑셀·CSV 가져오기는 다음 업데이트에서 제공해요.</p>
        <button class="btn pick" @click="fileInput?.click()">파일 선택</button>
        <!-- 안드로이드 파일 선택기는 .json을 MIME으로 못 알아보는 경우가 있어 앱에서는 제한하지 않는다 -->
        <input ref="fileInput" type="file" hidden :accept="isNativeApp ? undefined : 'application/json,.json'" @change="onFile" />
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </template>

    <template v-else-if="file.encrypted && !incoming">
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
        <h2>마음장부 백업</h2>
        <p class="muted small">{{ fileName }}</p>
        <p class="big">사람 {{ preview.people }} · 행사 {{ preview.events }} · 기록 {{ preview.records }}건</p>
        <p v-if="preview.from" class="muted small">{{ formatDot(preview.from) }} ~ {{ formatDot(preview.to!) }}</p>
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
          <h2 class="section-title">같은 사람인지 확인해 주세요 ({{ conflicts.length }})</h2>
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
</style>
