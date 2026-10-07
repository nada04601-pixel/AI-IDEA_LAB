<script setup lang="ts">
import { ref, watch } from 'vue'
import { QUICK_AMOUNTS, formatFull, formatShort, parseAmount } from '../lib/money'

/** 금액 빠른 선택 (screens.md 4-4). 버튼은 금액만 채우고 저장하지 않는다. */
const model = defineModel<number | null>({ required: true })
const custom = ref(false)
const text = ref('')

watch(model, (v) => {
  if (v !== null && !QUICK_AMOUNTS.includes(v) && !custom.value) {
    custom.value = true
    text.value = String(v / 10000)
  }
}, { immediate: true })

function pick(v: number) {
  custom.value = false
  model.value = v
}

function openCustom() {
  custom.value = true
  text.value = model.value ? String(model.value / 10000) : ''
}

function onInput() {
  // 숫자만 입력하면 만원 단위 ("15" → 150,000원). "3만5천", "123,456원"도 이해한다.
  model.value = parseAmount(text.value, 'man')
}
</script>

<template>
  <div class="chips">
    <button
      v-for="v in QUICK_AMOUNTS"
      :key="v"
      type="button"
      class="chip amt"
      :aria-pressed="!custom && model === v"
      @click="pick(v)"
    >{{ formatShort(v) }}</button>
    <button type="button" class="chip amt" :aria-pressed="custom" @click="openCustom">직접</button>
  </div>
  <div v-if="custom" class="custom row">
    <input
      v-model="text"
      class="field grow"
      inputmode="decimal"
      placeholder="예: 15 (만원 단위)"
      aria-label="금액 직접 입력 (만원 단위)"
      @input="onInput"
    />
    <span class="muted">만원</span>
  </div>
  <p class="confirm" :class="{ muted: model === null }" aria-live="polite">
    {{ model === null ? '금액을 골라 주세요' : formatFull(model) }}
  </p>
</template>

<style scoped>
.amt { min-width: 56px; }
.custom { margin-top: 10px; }
.confirm { margin: 8px 2px 0; font-size: 1.15rem; font-weight: 800; font-variant-numeric: tabular-nums; }
</style>
