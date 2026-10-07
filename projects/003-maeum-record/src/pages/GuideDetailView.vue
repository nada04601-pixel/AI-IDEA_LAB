<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { findGuide } from '../content/guides'

/** S-07 가이드 상세. 하단에서 진료 준비(S-04)로 연결 (C → A) */
const route = useRoute()
const guide = computed(() => findGuide(String(route.params.slug)))
</script>

<template>
  <div class="page stack">
    <template v-if="guide">
      <h1>{{ guide.title }}</h1>
      <p v-if="guide.basedOn" class="muted">정보 기준일: {{ guide.basedOn }}</p>

      <p v-if="guide.draft" class="card muted">이 글은 준비 중이에요. 출처를 확인한 뒤 채워질 예정이에요.</p>
      <p v-for="(para, i) in guide.body" :key="i">{{ para }}</p>

      <section v-if="guide.links?.length">
        <h2>관련 공식 안내</h2>
        <ul class="list">
          <li v-for="l in guide.links" :key="l.url">
            <a :href="l.url" target="_blank" rel="noopener">{{ l.label }} ↗</a>
          </li>
        </ul>
      </section>

      <div class="card cta">
        <p>진료 때 보여줄 기록이 있으면 말하기가 쉬워져요.</p>
        <RouterLink class="btn" to="/visit">진료 준비하기 →</RouterLink>
      </div>
    </template>
    <p v-else class="muted">글을 찾을 수 없어요. <RouterLink to="/guides">목록으로</RouterLink></p>
  </div>
</template>

<style scoped>
.cta p { margin: 0 0 12px; }
</style>
