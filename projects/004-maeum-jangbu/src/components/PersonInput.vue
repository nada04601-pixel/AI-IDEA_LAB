<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger } from '../lib/store'
import { searchPeople } from '../lib/ledger'
import { relationLabel, type Person } from '../lib/types'

/**
 * 이름 입력 + 자동 완성 (screens.md S-07).
 * 기존 사람을 고르면 personId, 새 이름이면 null.
 */
const name = defineModel<string>('name', { required: true })
const personId = defineModel<string | null>('personId', { required: true })
defineProps<{ autofocus?: boolean }>()
const focused = ref(false)

const suggestions = computed(() => (personId.value ? [] : searchPeople(ledger.value.people, name.value)))
const exact = computed(() => ledger.value.people.some((p) => p.name === name.value.trim()))

function choose(p: Person) {
  name.value = p.name
  personId.value = p.id
  focused.value = false
}

function onBlur() {
  setTimeout(() => (focused.value = false), 150)
}

function onInput() {
  personId.value = null
}
</script>

<template>
  <div class="wrap">
    <input
      v-model="name"
      class="field"
      placeholder="이름"
      autocomplete="off"
      :autofocus="autofocus"
      aria-label="이름"
      @input="onInput"
      @focus="focused = true"
      @blur="onBlur"
    />
    <span v-if="personId" class="picked badge accent">기존 사람</span>
    <ul v-if="focused && name.trim() && !personId" class="suggest card flush list">
      <li v-for="p in suggestions" :key="p.id">
        <button type="button" class="list-row" @mousedown.prevent="choose(p)">
          <span><strong>{{ p.name }}</strong> <span class="muted small">{{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</span></span>
        </button>
      </li>
      <li v-if="!exact || suggestions.length">
        <button type="button" class="list-row new" @mousedown.prevent="focused = false">+ "{{ name.trim() }}" 새 사람으로 추가</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.wrap { position: relative; }
.picked { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); }
.suggest { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30; box-shadow: 0 6px 18px rgb(0 0 0 / 0.12); max-height: 260px; overflow-y: auto; }
.suggest .list-row { padding: 11px 14px; }
.new { color: var(--accent); font-weight: 700; }
</style>
