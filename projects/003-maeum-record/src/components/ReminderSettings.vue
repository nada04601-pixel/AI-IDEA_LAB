<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { disableReminder, enableReminder, getReminder, setReminderTime } from '../lib/reminder'
import { DEFAULT_REMINDER_TIME } from '../lib/reminderSchedule'
import { formatTime } from '../lib/date'

/** 설정(S-09)의 기록 알림 항목. 안드로이드 앱에서만 표시한다. */
const enabled = ref(false)
const time = ref(DEFAULT_REMINDER_TIME)
const message = ref<string | null>(null)
const busy = ref(false)

onMounted(async () => {
  const r = await getReminder()
  enabled.value = r.enabled
  time.value = r.time
})

async function toggle() {
  busy.value = true
  message.value = null
  try {
    if (enabled.value) {
      await disableReminder()
      enabled.value = false
    } else {
      const res = await enableReminder(time.value)
      enabled.value = res === 'enabled'
      if (res === 'denied') message.value = '알림 권한이 없어요. 휴대폰 설정 → 앱 → 마음기록 → 알림에서 허용해 주세요.'
    }
  } finally {
    busy.value = false
  }
}

async function changeTime() {
  if (!time.value) return
  await setReminderTime(time.value)
  if (enabled.value) message.value = `매일 ${formatTime(time.value)}에 알려드릴게요.`
}
</script>

<template>
  <div class="card">
    <div class="row">
      <span>기록 알림</span>
      <button class="switch" role="switch" :aria-checked="enabled" :disabled="busy" @click="toggle">
        <span class="knob" />
      </button>
    </div>
    <label class="row time-row">
      <span class="muted">알림 시간</span>
      <input v-model="time" type="time" class="field time" @change="changeTime" />
    </label>
    <p class="muted small">하루 한 번만 보내요. 그날 이미 기록했다면 보내지 않아요.</p>
    <p v-if="message" class="msg small" role="status">{{ message }}</p>
  </div>
</template>

<style scoped>
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.time-row { margin-top: 12px; }
.time { width: auto; padding: 8px 10px; }
.small { font-size: 0.85rem; margin: 10px 0 0; }
.msg { color: var(--help); }
.switch {
  position: relative; width: 52px; height: 30px; border-radius: 999px; border: 0;
  background: var(--line); transition: background 0.15s; flex-shrink: 0;
}
.switch[aria-checked='true'] { background: var(--accent); }
.knob {
  position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%;
  background: #fff; transition: transform 0.15s; box-shadow: 0 1px 3px rgb(0 0 0 / 0.2);
}
.switch[aria-checked='true'] .knob { transform: translateX(22px); }
</style>
