<script setup lang="ts">
import { CHECKED_ON, CONTACTS, telHref } from '../content/help'

/** S-08 도움받을 곳. 번호는 앱에 내장되어 오프라인에서도 열린다. */
</script>

<template>
  <div class="page stack">
    <h1>지금 이야기할 곳이 필요하다면</h1>
    <p class="muted">혼자 견디지 않아도 괜찮아요. 아래 번호는 누르면 바로 전화가 연결돼요.</p>

    <ul class="list card flush">
      <li v-for="c in CONTACTS" :key="c.number">
        <a class="list-row contact" :href="telHref(c.number)">
          <span>
            <span class="name">{{ c.name }}</span><br />
            <span class="number">{{ c.number }}</span>
            <span v-if="c.note" class="muted"> · {{ c.note }}</span>
          </span>
          <span class="call" aria-hidden="true">📞</span>
        </a>
      </li>
    </ul>

    <p class="muted small">정보 확인일: {{ CHECKED_ON }}</p>
  </div>
</template>

<style scoped>
.flush { padding: 0; }
.contact { padding: 16px; }
.name { font-weight: 600; }
.number { font-size: 1.25rem; font-weight: 700; color: var(--help); font-variant-numeric: tabular-nums; }
.call { font-size: 1.5rem; }
.small { font-size: 0.82rem; }
</style>
