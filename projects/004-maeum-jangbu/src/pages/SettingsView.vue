<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSetting, setSetting, wipeAll } from '../lib/db'
import { DEFAULT_NOTIFY, type NotifySettings } from '../lib/notifySchedule'
import { ensureNotifyPermission, getNotifySettings, notifySupported, saveNotifySettings } from '../lib/notify'
import { ask } from '../lib/dialog'
import { setFontSize, type FontSize } from '../lib/prefs'
import { resetOnboarded } from '../router'
import { isNativeApp } from '../lib/platform'
import { showToast } from '../lib/toast'

/** S-13 설정 */
const router = useRouter()
const s = ref<NotifySettings>({ ...DEFAULT_NOTIFY })
const font = ref<FontSize>('normal')
const version = __APP_BUILD__

onMounted(async () => {
  s.value = await getNotifySettings()
  font.value = await getSetting<FontSize>('fontSize', 'normal')
})

async function update(patch: Partial<NotifySettings>) {
  if ((patch.eventEnabled || patch.backupEnabled) && notifySupported && !(await ensureNotifyPermission())) {
    showToast('휴대폰 설정에서 마음장부 알림을 허용해 주세요', 3000)
  }
  s.value = { ...s.value, ...patch }
  await saveNotifySettings(patch)
}

async function changeFont(f: FontSize) {
  font.value = f
  await setFontSize(f)
}

async function wipe() {
  const choice = await ask('모든 기록을 삭제할까요?', '삭제하면 되돌릴 수 없어요. 먼저 백업해 두는 것을 권해요.', [
    { label: '취소', value: 'cancel' },
    { label: '백업하고 삭제', value: 'backup', primary: true },
    { label: '그냥 삭제', value: 'wipe' },
  ])
  if (choice === 'backup') return router.push('/backup')
  if (choice !== 'wipe') return
  const typed = prompt('정말 삭제하려면 “삭제”를 입력해 주세요.')
  if (typed?.trim() !== '삭제') return
  await wipeAll()
  await saveNotifySettings({})
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
  <div class="page">
    <h2 class="section-title">데이터</h2>
    <div class="card flush">
      <ul class="list">
        <li><RouterLink to="/backup" class="list-row">내보내기·백업 <span aria-hidden="true">›</span></RouterLink></li>
        <li><RouterLink to="/bulk" class="list-row">엑셀·CSV로 한꺼번에 등록 <span aria-hidden="true">›</span></RouterLink></li>
        <li><RouterLink to="/restore" class="list-row">가져오기·복원 <span aria-hidden="true">›</span></RouterLink></li>
        <li><RouterLink to="/move" class="list-row">새 휴대폰으로 옮기기 <span aria-hidden="true">›</span></RouterLink></li>
        <li class="list-row">
          <span>백업 알림<br /><span class="muted small">마지막 백업 후 {{ s.backupDays }}일이 지나면 알려 드려요</span></span>
          <input type="checkbox" class="switch" :checked="s.backupEnabled" aria-label="백업 알림" @change="update({ backupEnabled: ($event.target as HTMLInputElement).checked })" />
        </li>
      </ul>
    </div>

    <h2 class="section-title">알림 <span v-if="!notifySupported" class="badge">앱에서 제공</span></h2>
    <div class="card flush">
      <ul class="list">
        <li class="list-row">
          <span>경조사 알림<br /><span class="muted small">알림을 켠 상대 경조사만 알려 드려요</span></span>
          <input type="checkbox" class="switch" :checked="s.eventEnabled" aria-label="경조사 알림" @change="update({ eventEnabled: ($event.target as HTMLInputElement).checked })" />
        </li>
        <li class="list-row">
          <span>알림 시점</span>
          <span class="row">
            <select class="field mini" :value="s.daysBefore" aria-label="며칠 전" @change="update({ daysBefore: Number(($event.target as HTMLSelectElement).value) })">
              <option :value="0">당일</option>
              <option :value="1">하루 전</option>
              <option :value="3">3일 전</option>
              <option :value="7">일주일 전</option>
            </select>
            <input class="field mini" type="time" :value="s.time" aria-label="시각" @change="update({ time: ($event.target as HTMLInputElement).value || '09:00' })" />
          </span>
        </li>
      </ul>
    </div>
    <p v-if="!notifySupported" class="muted small note">웹 버전에서는 알림을 보낼 수 없어요. 안드로이드 앱에서 쓸 수 있어요.</p>

    <h2 class="section-title">화면</h2>
    <div class="card">
      <span class="label">글자 크기</span>
      <div class="segment" role="group" aria-label="글자 크기">
        <button :aria-pressed="font === 'normal'" @click="changeFont('normal')">보통</button>
        <button :aria-pressed="font === 'large'" @click="changeFont('large')">크게</button>
        <button :aria-pressed="font === 'xlarge'" @click="changeFont('xlarge')">아주 크게</button>
      </div>
    </div>

    <h2 class="section-title">정보</h2>
    <div class="card about">
      <p><strong>이 앱은 인터넷에 연결하지 않아요.</strong></p>
      <p class="muted small">모든 기록은 이 휴대폰에만 저장되고 어디로도 보내지 않아요. 회원가입도 없어요. 그래서 백업 파일을 직접 보관해 주셔야 해요.</p>
    </div>
    <div class="card flush links">
      <ul class="list">
        <li><RouterLink to="/privacy" class="list-row">개인정보처리방침 <span aria-hidden="true">›</span></RouterLink></li>
        <li><button class="list-row" @click="replayWelcome">첫 실행 안내 다시 보기 <span aria-hidden="true">›</span></button></li>
        <li><button class="list-row" @click="wipe">모든 기록 삭제 <span aria-hidden="true">›</span></button></li>
      </ul>
    </div>
    <p class="muted small ver">마음장부 버전 {{ version }} ({{ isNativeApp ? '안드로이드 테스트' : '웹' }})</p>
  </div>
</template>

<style scoped>
.switch { width: 46px; height: 26px; accent-color: var(--accent); flex: none; }
.mini { width: auto; padding: 8px; }
.note { margin: 8px 4px 0; }
.about p { margin: 0 0 6px; }
.links { margin-top: 10px; }
.ver { margin: 16px 4px; }
</style>
