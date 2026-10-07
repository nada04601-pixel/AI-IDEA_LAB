<script setup lang="ts">
/** 사진으로 등록 — 개발 4단계 (OCR 사전 테스트 후, tech-stack.md 4장) */
</script>

<template>
  <div class="page no-tab soon">
    <div class="icon" aria-hidden="true">📷</div>
    <h1>사진으로 지난 기록 등록</h1>
    <span class="badge accent">다음 업데이트에서 제공</span>
    <p class="muted">이체 내역 캡처, 축의금 대장, 종이 장부 사진을 글자로 바꿔 한 번에 등록하는 기능을 만들고 있어요. 사진은 휴대폰 안에서만 읽고 어디로도 보내지 않아요.</p>
    <RouterLink to="/quick" class="btn secondary">지금은 명단 빠르게 입력하기</RouterLink>
    <RouterLink to="/restore" class="btn outline">엑셀로 정리해 둔 명단 가져오기</RouterLink>
  </div>
</template>

<style scoped>
.soon { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 12px; padding-top: 48px; }
.icon { font-size: 3rem; }
.soon p { max-width: 340px; }
.soon .btn { max-width: 340px; }
</style>
