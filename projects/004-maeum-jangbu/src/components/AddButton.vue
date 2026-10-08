<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

/** [+ 기록] 버튼과 등록 방법 시트 (screens.md 3. 화면 이동 흐름) */
const open = ref(false)
const router = useRouter()

const items = [
  { icon: '✍', label: '받은 돈 / 보낸 돈 1건', desc: '한 사람의 기록을 남겨요', to: '/record' },
  { icon: '✉', label: '상대 경조사 등록', desc: '청첩장·부고를 받았을 때', to: '/record?mode=theirs' },
  { icon: '💍', label: '내 행사 명단 빠르게 입력', desc: '방명록을 보며 연달아 입력해요', to: '/quick' },
  { icon: '📷', label: '사진으로 등록', desc: '이체 내역·장부 사진을 글자로', to: '/ocr' },
  { icon: '📄', label: '엑셀·CSV에서 가져오기', desc: '정리해 둔 파일이 있다면', to: '/restore' },
]

function go(to: string) {
  open.value = false
  router.push(to)
}
</script>

<template>
  <button class="fab" @click="open = true">+ 기록</button>
  <Teleport to="body">
    <div v-if="open" class="backdrop" @click.self="open = false">
      <div class="sheet" role="dialog" aria-label="기록 방법 고르기">
        <div class="between head">
          <h2>무엇을 기록할까요?</h2>
          <button class="close" aria-label="닫기" @click="open = false">✕</button>
        </div>
        <ul class="list">
          <li v-for="it in items" :key="it.to">
            <button class="list-row" @click="go(it.to)">
              <span class="ic" aria-hidden="true">{{ it.icon }}</span>
              <span class="grow">
                <strong>{{ it.label }}</strong><br />
                <span class="muted small">{{ it.desc }}</span>
              </span>
              <span aria-hidden="true">›</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.fab {
  position: fixed; z-index: 15;
  right: max(16px, calc(50% - 240px + 16px)); bottom: calc(var(--tab-h) + 16px + env(safe-area-inset-bottom));
  border: 0; border-radius: 999px; padding: 14px 20px; font-weight: 800;
  background: var(--accent); color: var(--accent-text); box-shadow: 0 4px 14px rgb(0 0 0 / 0.18);
}
.backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.35); z-index: 40; display: flex; align-items: flex-end; justify-content: center; }
.sheet {
  width: 100%; max-width: 480px; background: var(--surface); border-radius: 18px 18px 0 0;
  padding: 16px 4px calc(16px + env(safe-area-inset-bottom));
}
.head { padding: 0 12px 4px 16px; }
.head h2 { margin: 0; }
.close { border: 0; background: none; font-size: 1.2rem; width: 40px; height: 40px; }
.ic { font-size: 1.4rem; width: 32px; text-align: center; }
</style>
