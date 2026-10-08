<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger } from '../lib/store'
import { formatDot } from '../lib/date'
import { relationLabel } from '../lib/types'

/** 전체 검색: 이름, 행사명, 메모 (screens.md 4-1) */
const q = ref('')
const s = computed(() => q.value.trim())
const people = computed(() =>
  s.value ? ledger.value.people.filter((p) => p.name.includes(s.value) || p.group.includes(s.value) || p.memo.includes(s.value)).slice(0, 30) : [],
)
const events = computed(() =>
  s.value ? ledger.value.events.filter((e) => e.title.includes(s.value) || e.place.includes(s.value)).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 30) : [],
)
</script>

<template>
  <div class="page no-tab">
    <input v-model="q" class="field" type="search" placeholder="이름, 행사, 메모 검색" aria-label="검색" autofocus />
    <template v-if="s">
      <h2 class="section-title">사람 {{ people.length }}</h2>
      <div v-if="people.length" class="card flush">
        <ul class="list">
          <li v-for="p in people" :key="p.id">
            <RouterLink :to="`/people/${p.id}`" class="list-row"><span><strong>{{ p.name }}</strong> <span class="muted small">{{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</span></span><span aria-hidden="true">›</span></RouterLink>
          </li>
        </ul>
      </div>
      <h2 class="section-title">행사 {{ events.length }}</h2>
      <div v-if="events.length" class="card flush">
        <ul class="list">
          <li v-for="e in events" :key="e.id">
            <RouterLink :to="`/events/${e.id}`" class="list-row"><span>{{ e.title }} <span class="muted small">{{ formatDot(e.date) }}</span></span><span aria-hidden="true">›</span></RouterLink>
          </li>
        </ul>
      </div>
      <p v-if="!people.length && !events.length" class="muted">찾는 결과가 없어요.</p>
    </template>
  </div>
</template>
