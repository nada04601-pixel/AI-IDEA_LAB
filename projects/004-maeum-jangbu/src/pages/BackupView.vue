<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ledger } from '../lib/store'
import { getSetting, loadAll, markBackedUp } from '../lib/db'
import { backupFileName, makeBackupText } from '../lib/backup'
import { shareFile } from '../lib/share'
import { ask } from '../lib/dialog'
import { todayKey } from '../lib/date'
import { isNativeApp } from '../lib/platform'
import { showToast } from '../lib/toast'

/** S-11 내보내기·백업 */
const lastBackupAt = ref<number | null>(null)
const usePassword = ref(false)
const pw1 = ref('')
const pw2 = ref('')
const busy = ref(false)
const message = ref<string | null>(null)

onMounted(async () => (lastBackupAt.value = await getSetting<number | null>('lastBackupAt', null)))

const lastText = computed(() => {
  if (!lastBackupAt.value) return '아직 없음'
  const d = new Date(lastBackupAt.value)
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`
})

async function makeBackup() {
  message.value = null
  if (usePassword.value) {
    if (pw1.value.length < 4) return showToast('비밀번호는 4자 이상으로 정해 주세요')
    if (pw1.value !== pw2.value) return showToast('비밀번호가 서로 달라요')
  } else {
    // 비밀번호 없이 공유할 때는 매번 안내 (2026-10-07 결정)
    const choice = await ask('비밀번호 없이 백업할까요?', '이 파일에는 이름과 금액이 그대로 들어 있어요.\n카카오톡·이메일로 보내면 파일을 받은 사람도 볼 수 있어요.', [
      { label: '비밀번호 걸기', value: 'pw', cancel: true },
      { label: '그대로 백업하기', value: 'go', primary: true },
    ])
    if (choice === 'pw') {
      usePassword.value = true
      return
    }
  }
  busy.value = true
  try {
    const data = await loadAll()
    const text = await makeBackupText(data, usePassword.value ? pw1.value : undefined)
    const res = await shareFile(backupFileName(todayKey()), text, 'application/json', '마음장부 백업')
    if (res === 'canceled') {
      message.value = '백업을 취소했어요.'
      return
    }
    await markBackedUp()
    lastBackupAt.value = Date.now()
    pw1.value = pw2.value = ''
    message.value = isNativeApp
      ? `기록 ${data.records.length}건을 백업했어요. 고른 곳에 잘 저장됐는지 확인해 주세요.`
      : `기록 ${data.records.length}건을 백업 파일로 내려받았어요.`
  } catch (e) {
    message.value = `백업 파일을 만들지 못했어요. (${(e as Error).message})`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page no-tab">
    <section class="card">
      <h2>전체 백업</h2>
      <p class="muted">사람 {{ ledger.people.length }} · 행사 {{ ledger.events.length }} · 기록 {{ ledger.records.length }}</p>
      <p class="muted small">마지막 백업: {{ lastText }}</p>

      <label class="row pwtoggle">
        <input v-model="usePassword" type="checkbox" /> 비밀번호 걸기 <span class="muted small">(선택)</span>
      </label>
      <div v-if="usePassword" class="pw">
        <input v-model="pw1" class="field" type="password" autocomplete="new-password" placeholder="비밀번호" aria-label="비밀번호" />
        <input v-model="pw2" class="field" type="password" autocomplete="new-password" placeholder="한 번 더" aria-label="비밀번호 확인" />
        <p class="warn small">ⓘ 비밀번호를 잊으면 이 백업은 복원할 수 없어요. 서버가 없어서 찾아 드릴 방법이 없어요.</p>
      </div>

      <button class="btn make" :disabled="busy" @click="makeBackup">{{ busy ? '만드는 중…' : '백업 파일 만들기' }}</button>
      <p class="muted small">{{ isNativeApp ? '카카오톡 나에게, 드라이브, 이메일 중에서 저장할 곳을 고를 수 있어요.' : '백업 파일을 내려받아요.' }}</p>
      <p v-if="message" class="msg" role="status">{{ message }}</p>
    </section>

    <h2 class="section-title">보기 좋은 파일로 내보내기</h2>
    <RouterLink to="/export" class="card plain between">
      <span><strong>엑셀 · CSV · PDF 명단</strong><br /><span class="muted small">전체 내역 · 사람별 장부 · 행사별 명단</span></span>
      <span aria-hidden="true">›</span>
    </RouterLink>

    <h2 class="section-title">다른 곳에서 가져오기</h2>
    <div class="card flush">
      <ul class="list">
        <li><RouterLink to="/restore" class="list-row">백업 파일에서 복원 <span aria-hidden="true">›</span></RouterLink></li>
        <li><RouterLink to="/move" class="list-row">새 휴대폰으로 옮기기 안내 <span aria-hidden="true">›</span></RouterLink></li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.card h2 { margin-bottom: 4px; }
.card p { margin: 0 0 4px; }
.pwtoggle { margin-top: 14px; }
.pwtoggle input { width: 20px; height: 20px; }
.pw { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.warn { color: var(--warn); background: var(--warn-soft); padding: 10px 12px; border-radius: 10px; margin: 0; }
.make { margin: 16px 0 8px; }
.msg { margin-top: 10px !important; font-weight: 600; }
.plain { text-decoration: none; color: var(--text); }
</style>
