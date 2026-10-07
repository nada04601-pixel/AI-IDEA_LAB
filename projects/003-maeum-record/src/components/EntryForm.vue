<script setup lang="ts">
import { ref, watch } from 'vue'
import { MEMO_MAX, MOODS, TAGS, type Mood } from '../lib/mood'

/** S-02 기분 선택 → (선택) 메모·태그 → 저장. 홈과 달력 시트에서 같이 쓴다. */
const props = defineProps<{
  initial?: { mood: Mood; memo: string; tags: string[] }
  submitLabel?: string
  question?: string
}>()
const emit = defineEmits<{ submit: [{ mood: Mood; memo: string; tags: string[] }]; cancel: [] }>()

const mood = ref<Mood | null>(props.initial?.mood ?? null)
const memo = ref(props.initial?.memo ?? '')
const tags = ref<string[]>([...(props.initial?.tags ?? [])])

watch(
  () => props.initial,
  (v) => {
    mood.value = v?.mood ?? null
    memo.value = v?.memo ?? ''
    tags.value = [...(v?.tags ?? [])]
  },
)

function toggleTag(t: string) {
  tags.value = tags.value.includes(t) ? tags.value.filter((x) => x !== t) : [...tags.value, t]
}

function submit() {
  if (mood.value === null) return
  emit('submit', { mood: mood.value, memo: memo.value.slice(0, MEMO_MAX), tags: tags.value })
  if (!props.initial) {
    mood.value = null
    memo.value = ''
    tags.value = []
  }
}
</script>

<template>
  <form class="entry-form" @submit.prevent="submit">
    <p class="question">{{ question ?? '지금 기분은 어때요?' }}</p>
    <div class="moods" role="radiogroup" aria-label="기분">
      <button
        v-for="m in MOODS"
        :key="m.value"
        type="button"
        role="radio"
        class="mood"
        :aria-checked="mood === m.value"
        :style="{ '--c': m.color }"
        @click="mood = m.value"
      >
        <span class="emoji" aria-hidden="true">{{ m.emoji }}</span>
        <span class="label">{{ m.label }}</span>
      </button>
    </div>

    <div v-if="mood !== null" class="more stack">
      <label class="block">
        <span class="muted">한 줄 메모 (선택)</span>
        <input v-model="memo" class="field" :maxlength="MEMO_MAX" placeholder="쓰지 않아도 괜찮아요" />
      </label>
      <div>
        <span class="muted">태그 (선택)</span>
        <div class="chips" style="margin-top: 6px">
          <button v-for="t in TAGS" :key="t" type="button" class="chip" :aria-pressed="tags.includes(t)" @click="toggleTag(t)">
            {{ t }}
          </button>
        </div>
      </div>
      <button type="submit" class="btn">{{ submitLabel ?? '기록하기' }}</button>
      <button v-if="initial" type="button" class="btn secondary" @click="emit('cancel')">취소</button>
    </div>
  </form>
</template>

<style scoped>
.question { font-size: 1.15rem; font-weight: 600; margin: 0 0 14px; }
.moods { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.mood {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 10px 2px; border-radius: 12px; border: 2px solid transparent; background: var(--surface-2);
}
.mood[aria-checked='true'] { border-color: var(--c); background: var(--surface); }
.emoji { font-size: 2rem; line-height: 1.1; }
.label { font-size: 0.74rem; color: var(--text-2); white-space: nowrap; }
.more { margin-top: 18px; }
.block { display: flex; flex-direction: column; gap: 6px; }
</style>
