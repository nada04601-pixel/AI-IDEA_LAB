<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { allEntries, replaceAllEntries, setSetting, wipeAll } from '../lib/db'
import { lastBackupLabel, mergeEntries, parseBackup } from '../lib/backup'
import { exportBackup as doExport, getLastBackupAt } from '../lib/backupExport'
import { resetOnboarded } from '../router'
import { isNativeApp } from '../lib/platform'
import ReminderSettings from '../components/ReminderSettings.vue'
import { syncReminder } from '../lib/reminder'

/** S-09 설정 */
const router = useRouter()
const message = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const version = __APP_BUILD__
const lastBackup = ref('…')
const exporting = ref(false)

const refreshLastBackup = async () => (lastBackup.value = lastBackupLabel(await getLastBackupAt()))
onMounted(refreshLastBackup)

async function exportBackup() {
  exporting.value = true
  message.value = null
  try {
    const res = await doExport()
    if (res.status === 'saved') {
      message.value = isNativeApp
        ? `기록 ${res.count}개를 백업 파일로 만들었어요. 고른 곳에 잘 저장됐는지 확인해 주세요.`
        : `기록 ${res.count}개를 백업 파일로 만들었어요.`
      await refreshLastBackup()
    } else {
      message.value = '백업을 취소했어요.'
    }
  } catch (e) {
    message.value = `백업 파일을 만들지 못했어요. (${(e as Error).message})`
  } finally {
    exporting.value = false
  }
}

async function importBackup(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const backup = parseBackup(await file.text())
    const replace = confirm(
      `백업 파일에 기록 ${backup.entries.length}개가 있어요.\n\n[확인] 지금 기록을 지우고 덮어쓰기\n[취소] 지금 기록과 합치기`,
    )
    const { result, added, skipped } = mergeEntries(await allEntries(), backup.entries, replace ? 'replace' : 'merge')
    await replaceAllEntries(result)
    void syncReminder()
    message.value = replace ? `기록 ${added}개로 덮어썼어요.` : `기록 ${added}개를 합쳤어요. (중복 ${skipped}개 제외)`
  } catch (e) {
    message.value = (e as Error).message
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function wipe() {
  const typed = prompt('모든 기록을 삭제해요. 되돌릴 수 없어요.\n계속하려면 “삭제”를 입력해 주세요.')
  if (typed?.trim() !== '삭제') return
  await wipeAll()
  await syncReminder() // 설정도 지워졌으므로 예약된 알림 취소
  resetOnboarded()
  router.replace('/welcome')
}

async function replayWelcome() {
  await setSetting('onboardingDone', false)
  resetOnboarded()
  router.push('/welcome')
}
</script>

<template>
  <div class="page stack">
    <section>
      <h2 class="section">알림</h2>
      <ReminderSettings v-if="isNativeApp" />
      <div v-else class="card">
        <p class="row">기록 알림 <span class="badge">앱에서 제공</span></p>
        <p class="muted small">웹 버전에서는 정해진 시간에 알림을 보낼 수 없어요. 안드로이드 앱에서는 쓸 수 있어요.</p>
      </div>
    </section>

    <section>
      <h2 class="section">데이터</h2>
      <ul class="list card flush">
        <li>
          <button class="list-row" :disabled="exporting" @click="exportBackup">
            <span>기록 백업 파일 만들기<br /><span class="muted small">마지막 백업: {{ lastBackup }}</span></span>
            <span aria-hidden="true">›</span>
          </button>
        </li>
        <li>
          <button class="list-row" @click="fileInput?.click()">백업 파일에서 불러오기 <span aria-hidden="true">›</span></button>
          <!-- 안드로이드 파일 선택기는 .json을 MIME으로 못 알아보는 경우가 있어 앱에서는 제한하지 않는다 (내용은 parseBackup이 검사) -->
          <input ref="fileInput" type="file" :accept="isNativeApp ? undefined : 'application/json,.json'" hidden @change="importBackup" />
        </li>
        <li><button class="list-row" @click="wipe">모든 기록 삭제 <span aria-hidden="true">›</span></button></li>
      </ul>
      <p v-if="message" class="muted msg" role="status">{{ message }}</p>
      <p class="muted small hint">백업 파일에는 기록 내용이 그대로 들어 있어요. 믿을 수 있는 곳에만 저장해 주세요.</p>
    </section>

    <section>
      <h2 class="section">앱</h2>
      <ul class="list card flush">
        <li><button class="list-row" @click="replayWelcome">첫 실행 안내 다시 보기 <span aria-hidden="true">›</span></button></li>
      </ul>
      <div class="card about">
        <h2>이 앱에 대하여</h2>
        <p class="muted small">마음기록은 기분을 기록하고 진료·상담에 가져갈 수 있게 돕는 도구예요. 치료를 대신하지 않아요. 모든 기록은 이 기기에만 저장되고 서버로 보내지 않아요.</p>
      </div>
    </section>

    <p class="muted small">버전 {{ version }} ({{ isNativeApp ? '안드로이드 테스트' : '웹' }})</p>
  </div>
</template>

<style scoped>
.section { color: var(--text-2); font-size: 0.9rem; margin: 8px 0; }
.flush { padding: 0; }
.row { display: flex; justify-content: space-between; align-items: center; margin: 0 0 4px; }
.small { font-size: 0.85rem; margin: 0; }
.msg { margin-top: 8px; }
.hint { margin-top: 8px; }
.about { margin-top: 12px; }
</style>
