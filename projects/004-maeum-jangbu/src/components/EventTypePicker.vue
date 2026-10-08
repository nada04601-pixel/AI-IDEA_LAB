<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ledger } from '../lib/store'
import { CUSTOM_TYPE_MAX, EVENT_TYPES, type EventType } from '../lib/types'

/**
 * 행사 종류 고르기. 정해진 종류 + "직접 입력" (예: 칠순, 집들이, 졸업).
 * 예전에 직접 입력한 종류는 버튼으로 다시 고를 수 있다.
 */
const type = defineModel<EventType>('type', { required: true })
const customType = defineModel<string>('customType', { required: true })

const standard = EVENT_TYPES.filter((t) => t.value !== 'other')
const typing = ref(type.value === 'other' && !recentHas(customType.value))
const inputEl = ref<HTMLInputElement | null>(null)

/** 최근에 직접 입력한 종류 (중복 없이 최신순 6개) */
const recent = computed(() => {
  const seen = new Set<string>()
  return [...ledger.value.events]
    .sort((a, b) => b.createdAt - a.createdAt)
    .map((e) => (e.type === 'other' ? (e.customType?.trim() ?? '') : ''))
    .filter((c) => c && !seen.has(c) && seen.add(c))
    .slice(0, 6)
})
function recentHas(c: string) {
  return !!c && ledger.value.events.some((e) => e.type === 'other' && e.customType?.trim() === c)
}

function pick(t: EventType) {
  type.value = t
  customType.value = ''
  typing.value = false
}
function pickRecent(c: string) {
  type.value = 'other'
  customType.value = c
  typing.value = false
}
async function startTyping() {
  type.value = 'other'
  if (recentHas(customType.value)) customType.value = ''
  typing.value = true
  await nextTick()
  inputEl.value?.focus()
}
</script>

<template>
  <div class="chips">
    <button v-for="t in standard" :key="t.value" type="button" class="chip" :aria-pressed="type === t.value" @click="pick(t.value)">{{ t.icon }} {{ t.label }}</button>
    <button
      v-for="c in recent"
      :key="c"
      type="button"
      class="chip"
      :aria-pressed="type === 'other' && !typing && customType === c"
      @click="pickRecent(c)"
    >📌 {{ c }}</button>
    <button type="button" class="chip" :aria-pressed="type === 'other' && typing" @click="startTyping">✏ 직접 입력</button>
  </div>
  <input
    v-if="type === 'other' && typing"
    ref="inputEl"
    v-model="customType"
    class="field custom"
    :maxlength="CUSTOM_TYPE_MAX"
    placeholder="예: 칠순, 집들이, 졸업, 병문안"
    aria-label="행사 종류 직접 입력"
  />
</template>

<style scoped>
.custom { margin-top: 10px; }
</style>
