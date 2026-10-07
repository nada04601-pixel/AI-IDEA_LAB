<script setup lang="ts">
import { onMounted, ref } from 'vue'
import EntryForm from '../components/EntryForm.vue'
import { addEntry, entriesOn } from '../lib/db'
import { formatLong, formatTime, todayKey } from '../lib/date'
import { moodInfo, type Entry, type Mood } from '../lib/mood'
import { showToast, toastText } from '../lib/toast'
import { syncReminder } from '../lib/reminder'

/** S-02 홈 (오늘 기록) */
const today = todayKey()
const todays = ref<Entry[]>([])
const lastWasHardest = ref(false)

async function load() {
  todays.value = await entriesOn(today)
}

async function save(v: { mood: Mood; memo: string; tags: string[] }) {
  await addEntry(v)
  // 오늘 기록했으니 오늘 알림은 취소 (reminderSchedule.ts 규칙)
  void syncReminder()
  lastWasHardest.value = v.mood === 1
  showToast('기록했어요')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <p class="muted date">{{ formatLong(today) }}</p>

    <section class="card">
      <EntryForm @submit="save" />
      <!-- "아주 힘듦" 저장 후: 팝업으로 막지 않고 조용히 한 줄 (screens.md S-02 위기 대응) -->
      <p v-if="lastWasHardest" class="gentle">
        많이 힘든 날이네요.<br />
        이야기할 곳이 필요하면 → <RouterLink to="/help">도움받을 곳</RouterLink>
      </p>
    </section>

    <section v-if="todays.length" class="today">
      <h2>오늘 남긴 기록</h2>
      <ul class="list card flush">
        <li v-for="e in todays" :key="e.id" class="row">
          <span class="time">{{ formatTime(e.time) }}</span>
          <span class="emoji" :title="moodInfo(e.mood).label">{{ moodInfo(e.mood).emoji }}</span>
          <span class="text">
            <span v-if="e.memo">{{ e.memo }}</span>
            <span v-if="e.tags.length" class="muted"> {{ e.tags.map((t) => `#${t}`).join(' ') }}</span>
          </span>
        </li>
      </ul>
    </section>

    <div v-if="toastText" class="toast" role="status">{{ toastText }}</div>
  </div>
</template>

<style scoped>
.date { margin: 0 0 12px; }
.gentle { margin: 16px 0 0; padding-top: 14px; border-top: 1px solid var(--line); color: var(--text-2); }
.today { margin-top: 24px; }
.flush { padding: 0; }
.row { display: flex; align-items: flex-start; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
.row:last-child { border-bottom: 0; }
.time { color: var(--text-2); font-size: 0.88rem; min-width: 68px; padding-top: 2px; }
.emoji { font-size: 1.25rem; }
.text { flex: 1; word-break: break-all; }
</style>
