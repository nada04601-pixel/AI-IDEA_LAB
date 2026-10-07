<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

/** 다음 개발 단계 화면 (tech-stack.md 6장: 3 엑셀·PDF, 4 OCR) */
const route = useRoute()
const info = computed(() =>
  route.meta.feature === 'ocr'
    ? {
        icon: '📷',
        title: '사진으로 지난 기록 등록',
        body: '이체 내역 캡처, 축의금 대장, 종이 장부 사진을 글자로 바꿔 한 번에 등록하는 기능을 만들고 있어요. 사진은 휴대폰 안에서만 읽고 어디로도 보내지 않아요.',
        alt: { to: '/quick', label: '지금은 명단 빠르게 입력하기' },
      }
    : {
        icon: '📄',
        title: '엑셀 · CSV · PDF 내보내기',
        body: '전체 내역, 사람별 장부, 행사별 명단을 보기 좋은 엑셀로 만들고, 답례 명단을 PDF로 저장하는 기능을 만들고 있어요.',
        alt: { to: '/backup', label: '지금은 백업 파일 만들기' },
      },
)
</script>

<template>
  <div class="page no-tab soon">
    <div class="icon" aria-hidden="true">{{ info.icon }}</div>
    <h1>{{ info.title }}</h1>
    <span class="badge accent">다음 업데이트에서 제공</span>
    <p class="muted">{{ info.body }}</p>
    <RouterLink :to="info.alt.to" class="btn secondary">{{ info.alt.label }}</RouterLink>
  </div>
</template>

<style scoped>
.soon { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 12px; padding-top: 48px; }
.icon { font-size: 3rem; }
.soon p { max-width: 340px; }
</style>
