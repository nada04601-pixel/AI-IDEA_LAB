<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ledger, eventsById, peopleById } from '../lib/store'
import { addEvent, deleteEvent, updateEvent } from '../lib/db'
import { confirmAsk } from '../lib/dialog'
import { ensureNotifyPermission, notifySupported } from '../lib/notify'
import { showToast } from '../lib/toast'
import { todayKey } from '../lib/date'
import { EVENT_TYPES, defaultEventTitle, relationLabel, type EventOwner, type EventType } from '../lib/types'

/** 행사 추가·편집 */
const route = useRoute()
const router = useRouter()
const id = route.params.id ? String(route.params.id) : null
const existing = id ? eventsById.value.get(id) : undefined

const owner = ref<EventOwner>(existing?.owner ?? (route.query.owner === 'theirs' ? 'theirs' : 'mine'))
const type = ref<EventType>(existing?.type ?? 'wedding')
const personId = ref<string>(existing?.personId ?? '')
const date = ref(existing?.date ?? todayKey())
const place = ref(existing?.place ?? '')
const remind = ref(existing?.remind ?? true)
const title = ref(existing?.title ?? '')
const titleTouched = ref(!!existing)

const people = computed(() => [...ledger.value.people].sort((a, b) => a.name.localeCompare(b.name, 'ko')))
const autoTitle = computed(() => defaultEventTitle(owner.value, type.value, peopleById.value.get(personId.value)?.name))
const recordCount = computed(() => ledger.value.records.filter((r) => r.eventId === id).length)

async function save() {
  if (!date.value) return showToast('날짜를 입력해 주세요')
  if (owner.value === 'theirs' && !personId.value) return showToast('누구의 행사인지 골라 주세요')
  const data = {
    owner: owner.value,
    type: type.value,
    personId: owner.value === 'theirs' ? personId.value : null,
    date: date.value,
    place: place.value.trim(),
    remind: owner.value === 'theirs' && remind.value,
    title: (titleTouched.value && title.value.trim()) || autoTitle.value,
  }
  if (data.remind && notifySupported) await ensureNotifyPermission()
  if (id) {
    await updateEvent(id, data)
    router.back()
  } else {
    const e = await addEvent({ ...data, noRecordNeeded: false })
    router.replace(`/events/${e.id}`)
  }
  showToast('저장했어요')
}

async function remove() {
  if (!id) return
  const ok = await confirmAsk('행사를 삭제할까요?', `이 행사의 기록 ${recordCount.value}건도 함께 삭제돼요.`, '삭제')
  if (!ok) return
  await deleteEvent(id)
  showToast('삭제했어요')
  router.replace('/events')
}
</script>

<template>
  <div class="page no-tab">
    <span class="label">누구의 행사인가요?</span>
    <div class="segment" role="group">
      <button :aria-pressed="owner === 'mine'" @click="owner = 'mine'">내 행사</button>
      <button :aria-pressed="owner === 'theirs'" @click="owner = 'theirs'">상대 행사</button>
    </div>

    <template v-if="owner === 'theirs'">
      <label class="label" for="eperson">대상</label>
      <select id="eperson" v-model="personId" class="field">
        <option value="">사람 고르기</option>
        <option v-for="p in people" :key="p.id" :value="p.id">{{ p.name }} · {{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</option>
      </select>
      <p class="muted small">목록에 없는 사람은 [+ 기록] → 상대 경조사 등록에서 이름을 바로 입력할 수 있어요.</p>
    </template>

    <span class="label">종류</span>
    <div class="chips">
      <button v-for="t in EVENT_TYPES" :key="t.value" type="button" class="chip" :aria-pressed="type === t.value" @click="type = t.value">{{ t.icon }} {{ t.label }}</button>
    </div>

    <label class="label" for="edate">날짜</label>
    <input id="edate" v-model="date" type="date" class="field" />
    <label class="label" for="eplace">장소 <span class="muted small">(선택)</span></label>
    <input id="eplace" v-model="place" class="field" placeholder="예: ○○웨딩홀" />
    <label class="label" for="etitle">제목</label>
    <input id="etitle" v-model="title" class="field" :placeholder="autoTitle" @input="titleTouched = true" />

    <label v-if="owner === 'theirs'" class="row remind">
      <input v-model="remind" type="checkbox" /> D-day 알림 받기
      <span v-if="!notifySupported" class="badge">앱에서 제공</span>
    </label>

    <button class="btn save" @click="save">저장</button>
    <button v-if="id" class="btn outline delete" @click="remove">행사 삭제</button>
  </div>
</template>

<style scoped>
.remind { margin-top: 16px; }
.remind input { width: 20px; height: 20px; }
.save { margin-top: 20px; }
.delete { margin-top: 12px; }
</style>
