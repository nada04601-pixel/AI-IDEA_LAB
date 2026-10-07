<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { setSetting } from '../lib/db'
import { markOnboarded } from '../router'
import { isNativeApp } from '../lib/platform'
import { enableReminder } from '../lib/reminder'
import { DEFAULT_REMINDER_TIME } from '../lib/reminderSchedule'

/** S-01 첫 실행 안내 (3장) */
const router = useRouter()
const step = ref(0)

const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
const isStandalone =
  window.matchMedia?.('(display-mode: standalone)').matches || (navigator as { standalone?: boolean }).standalone === true
const showInstall = computed(() => !isStandalone && !isNativeApp)

const reminderTime = ref(DEFAULT_REMINDER_TIME)
const denied = ref(false)

async function turnOnReminder() {
  const res = await enableReminder(reminderTime.value || DEFAULT_REMINDER_TIME)
  if (res === 'denied') {
    // 거부해도 다시 묻지 않는다. 설정에서 켤 수 있다 (screens.md S-01)
    denied.value = true
    return
  }
  await finish()
}

async function finish() {
  await setSetting('onboardingDone', true)
  markOnboarded()
  router.replace('/')
}
</script>

<template>
  <div class="welcome">
    <button class="skip" @click="finish">건너뛰기</button>

    <section v-if="step === 0" class="slide">
      <div class="art" aria-hidden="true">🙂</div>
      <h1>하루 한 번,<br />기분을 남겨보세요.</h1>
      <p>모아둔 기록은 병원·상담에서 보여줄 수 있어요.</p>
      <p class="muted note">이 앱은 치료를 대신하지 않아요.</p>
    </section>

    <section v-else-if="step === 1" class="slide">
      <div class="art" aria-hidden="true">🔒</div>
      <h1>기록은 이 휴대폰에만<br />저장돼요.</h1>
      <p>회원가입이 없고, 기록을 서버로 보내지 않아요.</p>
      <p class="muted">휴대폰을 바꿀 땐 설정에서 백업 파일을 만들어 주세요.</p>
    </section>

    <section v-else class="slide">
      <div class="art" aria-hidden="true">🔔</div>
      <template v-if="isNativeApp">
        <h1>하루 한 번,<br />기록할 시간을 알려드릴까요?</h1>
        <p class="muted">그날 이미 기록했다면 알림을 보내지 않아요.</p>
        <label class="time-pick">
          <span>시간</span>
          <input v-model="reminderTime" type="time" class="field" />
        </label>
        <p v-if="denied" class="muted">알림이 허용되지 않았어요. 나중에 설정에서 켤 수 있어요.</p>
      </template>
      <template v-else>
        <h1>기록 알림은<br />앱 출시 후 제공돼요.</h1>
        <p class="muted">지금은 웹 버전이라 정해진 시간에 알림을 보낼 수 없어요.</p>
      </template>
      <div v-if="showInstall" class="card install">
        <h2>홈 화면에 추가하면 앱처럼 쓸 수 있어요</h2>
        <p v-if="isIOS" class="muted">Safari 아래쪽 공유 버튼 → “홈 화면에 추가”</p>
        <p v-else class="muted">브라우저 메뉴 → “앱 설치” 또는 “홈 화면에 추가”</p>
      </div>
    </section>

    <div class="footer">
      <div class="dots" aria-hidden="true">
        <span v-for="i in 3" :key="i" :class="{ on: step === i - 1 }" />
      </div>
      <button v-if="step < 2" class="btn" @click="step++">다음</button>
      <template v-else-if="isNativeApp && !denied">
        <button class="btn" @click="turnOnReminder">알림 켜기</button>
        <button class="later" @click="finish">나중에 할게요</button>
      </template>
      <button v-else class="btn" @click="finish">시작하기</button>
    </div>
  </div>
</template>

<style scoped>
.welcome { min-height: 100dvh; display: flex; flex-direction: column; padding: calc(16px + env(safe-area-inset-top)) 24px calc(24px + env(safe-area-inset-bottom)); }
.skip { align-self: flex-end; background: none; border: 0; color: var(--text-2); padding: 8px; }
.slide { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.art { font-size: 3.5rem; margin-bottom: 20px; }
h1 { font-size: 1.6rem; margin-bottom: 12px; }
p { margin: 0 0 8px; }
.note { margin-top: 24px; }
.install { margin-top: 24px; }
.time-pick { display: flex; align-items: center; gap: 12px; margin: 20px 0 12px; }
.time-pick .field { width: auto; }
.later { background: none; border: 0; color: var(--text-2); padding: 4px; margin-top: -6px; }
.footer { display: flex; flex-direction: column; gap: 16px; }
.dots { display: flex; gap: 6px; justify-content: center; }
.dots span { width: 7px; height: 7px; border-radius: 50%; background: var(--line); }
.dots span.on { background: var(--accent); }
</style>
