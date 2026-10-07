<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setSetting } from '../lib/db'
import { markOnboarded } from '../router'

/** S-01 첫 실행 안내 */
const step = ref(0)
const router = useRouter()

async function finish(to: string) {
  await setSetting('onboardingDone', true)
  markOnboarded()
  router.replace('/')
  if (to !== '/') router.push(to)
}
</script>

<template>
  <div class="welcome">
    <div class="top">
      <span class="dots" aria-hidden="true"><i v-for="i in 3" :key="i" :class="{ on: i - 1 === step }" /></span>
      <button v-if="step < 2" class="skip" @click="step = 2">건너뛰기</button>
    </div>

    <section v-if="step === 0" class="slide">
      <img src="/icon.svg" alt="" class="logo" />
      <h1>주고받은 마음을<br />한곳에 기록해요.</h1>
      <p class="muted">결혼식·장례식·돌잔치에서 받은 돈과 보낸 돈을 사람별로 모아 볼 수 있어요.</p>
      <p class="muted">예전에 얼마 받았는지 다시 찾지 않아도 돼요.</p>
      <button class="btn next" @click="step = 1">다음</button>
    </section>

    <section v-else-if="step === 1" class="slide">
      <div class="big" aria-hidden="true">📱</div>
      <h1>기록은 이 휴대폰에만<br />저장돼요.</h1>
      <p class="muted">회원가입이 없고, 인터넷에 연결하지 않아요.</p>
      <div class="card warn">
        <strong>그래서 백업이 중요해요.</strong><br />
        휴대폰을 바꾸거나 앱을 지우면 기록이 사라져요. 홈 화면에서 백업할 때를 알려 드릴게요.
      </div>
      <button class="btn next" @click="step = 2">다음</button>
    </section>

    <section v-else class="slide">
      <h1>무엇부터 할까요?</h1>
      <div class="stack choices">
        <button class="card choice" @click="finish('/ocr')"><span>📷</span><span><strong>사진으로 지난 기록 등록</strong><br /><span class="muted small">이체 내역·장부 사진을 글자로 바꿔요</span></span></button>
        <button class="card choice" @click="finish('/quick')"><span>💍</span><span><strong>내 행사 명단 정리하기</strong><br /><span class="muted small">결혼식 방명록을 보며 빠르게 입력</span></span></button>
        <button class="card choice" @click="finish('/record?mode=theirs')"><span>✉</span><span><strong>받은 청첩장·부고 등록하기</strong><br /><span class="muted small">날짜를 기억하고 알려 드려요</span></span></button>
      </div>
      <button class="btn outline" @click="finish('/')">둘러보기만 할게요</button>
    </section>
  </div>
</template>

<style scoped>
.welcome { min-height: 100dvh; display: flex; flex-direction: column; padding: calc(16px + env(safe-area-inset-top)) 20px calc(24px + env(safe-area-inset-bottom)); }
.top { display: flex; justify-content: space-between; align-items: center; min-height: 40px; }
.dots { display: flex; gap: 6px; }
.dots i { width: 8px; height: 8px; border-radius: 50%; background: var(--line); }
.dots i.on { background: var(--accent); width: 20px; border-radius: 4px; }
.skip { border: 0; background: none; color: var(--text-2); padding: 8px; }
.slide { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 14px; }
.slide h1 { font-size: 1.55rem; }
.slide p { margin: 0; }
.logo { width: 84px; height: 84px; }
.big { font-size: 3.2rem; }
.warn { background: var(--warn-soft); border-color: transparent; }
.next { margin-top: 16px; }
.choices { margin: 8px 0 12px; }
.choice { display: flex; gap: 14px; align-items: center; text-align: left; width: 100%; }
.choice > span:first-child { font-size: 1.7rem; }
</style>
