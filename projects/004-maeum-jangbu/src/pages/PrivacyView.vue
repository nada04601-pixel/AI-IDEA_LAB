<script setup lang="ts">
import policy from '../../PRIVACY.md?raw'
import { renderMarkdown } from '../lib/markdown'

/** 개인정보처리방침 — 저장소의 PRIVACY.md와 같은 내용 (스토어 등록용 공개 주소에도 같은 파일을 쓴다) */
const html = renderMarkdown(policy)
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html : 앱에 포함된 문서이며 renderMarkdown이 모든 글자를 이스케이프한다 -->
  <article class="page no-tab doc" v-html="html" />
</template>

<style scoped>
.doc :deep(h1) { font-size: 1.3rem; }
.doc :deep(h2) { font-size: 1.05rem; margin: 22px 0 6px; }
.doc :deep(p), .doc :deep(li) { color: var(--text); font-size: 0.95rem; }
.doc :deep(ul) { padding-left: 20px; margin: 6px 0; }
.doc :deep(li) { margin-bottom: 4px; }
</style>
