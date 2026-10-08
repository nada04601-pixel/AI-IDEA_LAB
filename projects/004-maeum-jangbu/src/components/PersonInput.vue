<script setup lang="ts">
import { computed, ref } from 'vue'
import { ledger } from '../lib/store'
import { sameName, searchPeople } from '../lib/ledger'
import { contactsSupported, pickContactName } from '../lib/contacts'
import { showToast } from '../lib/toast'
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

/** 연락처에서 1명 고르기 → 이름 채움. 장부에 같은 이름이 1명뿐이면 그 사람으로 */
async function fromContacts() {
  try {
    const n = await pickContactName()
    if (!n) return
    name.value = n
    const same = sameName(ledger.value.people, n)
    personId.value = same.length === 1 ? same[0].id : null
  } catch (e) {
    showToast(`연락처를 열지 못했어요 (${(e as Error).message})`, 3000)
  }
}

function onBlur() {
  setTimeout(() => (focused.value = false), 150)
}

function onInput() {
  personId.value = null
}
</script>

<template>
  <div class="wrap" :class="{ withc: contactsSupported }">
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
    <button v-if="contactsSupported" type="button" class="contact" aria-label="연락처에서 고르기" @click="fromContacts">📇</button>
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
.withc .field { padding-right: 52px; }
.withc .picked { right: 52px; }
.contact { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); width: 44px; height: 44px; border: 0; background: none; font-size: 1.25rem; }
.picked { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); }
.suggest { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30; box-shadow: 0 6px 18px rgb(0 0 0 / 0.12); max-height: 260px; overflow-y: auto; }
.suggest .list-row { padding: 11px 14px; }
.new { color: var(--accent); font-weight: 700; }
</style>
