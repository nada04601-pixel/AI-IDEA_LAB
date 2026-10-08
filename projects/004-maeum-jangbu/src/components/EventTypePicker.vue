<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ledger } from '../lib/store'
import { CUSTOM_TYPE_MAX, EVENT_TYPES, FUNERAL_KIN, FUNERAL_KIN_THEIRS_ONLY, type EventOwner, type EventType } from '../lib/types'

/**
 * 행사 종류 고르기. 정해진 종류 + "직접 입력" (예: 칠순, 집들이, 졸업).
 * 예전에 직접 입력한 종류는 버튼으로 다시 고를 수 있다.
 */
const type = defineModel<EventType>('type', { required: true })
const customType = defineModel<string>('customType', { required: true })
/** 장례일 때 누구의 상인지 (부친, 모친…). 제목에만 쓰고 따로 저장하지 않는다 */
const kin = defineModel<string>('kin', { default: '' })
const props = defineProps<{ owner?: EventOwner }>()
const kinOptions = computed(() => (props.owner === 'theirs' ? [...FUNERAL_KIN_THEIRS_ONLY, ...FUNERAL_KIN] : [...FUNERAL_KIN]))
const pickKin = (k: string) => (kin.value = kin.value === k ? '' : k)

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
  if (t !== 'funeral') kin.value = ''
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
  <div v-if="type === 'funeral'" class="kin">
    <span class="muted small">누구의 장례인가요? <span class="small">(선택)</span></span>
    <div class="chips">
      <button v-for="k in kinOptions" :key="k" type="button" class="chip" :aria-pressed="kin === k" @click="pickKin(k)">{{ k }}상</button>
    </div>
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
.kin { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
</style>
