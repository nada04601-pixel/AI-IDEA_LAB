<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ledger, peopleById } from '../lib/store'
import { addPerson, deletePerson, mergePeople, updatePerson } from '../lib/db'
import { confirmAsk } from '../lib/dialog'
import { showToast } from '../lib/toast'
import { contactsSupported, pickContactName } from '../lib/contacts'
import { RELATIONS, relationLabel, type Relation } from '../lib/types'

/** 사람 추가·편집 (S-03 사람 추가, S-04 편집·합치기) */
const route = useRoute()
const router = useRouter()
const id = route.params.id ? String(route.params.id) : null
const existing = id ? peopleById.value.get(id) : undefined

const name = ref(existing?.name ?? '')
const relation = ref<Relation>(existing?.relation ?? 'friend')
const group = ref(existing?.group ?? '')
const memo = ref(existing?.memo ?? '')
const mergeTarget = ref('')

const others = computed(() =>
  ledger.value.people
    .filter((p) => p.id !== id)
    .sort((a, b) => Number(b.name === name.value) - Number(a.name === name.value) || a.name.localeCompare(b.name, 'ko')),
)
const recordCount = computed(() => ledger.value.records.filter((r) => r.personId === id).length)

async function fromContacts() {
  try {
    const n = await pickContactName()
    if (n) name.value = n
  } catch (e) {
    showToast(`연락처를 열지 못했어요 (${(e as Error).message})`, 3000)
  }
}

async function save() {
  if (!name.value.trim()) return showToast('이름을 입력해 주세요')
  const data = { name: name.value.trim(), relation: relation.value, group: group.value.trim(), memo: memo.value.trim() }
  if (id) {
    await updatePerson(id, data)
    router.back()
  } else {
    const p = await addPerson(data)
    router.replace(`/people/${p.id}`)
  }
  showToast('저장했어요')
}

async function merge() {
  const target = peopleById.value.get(mergeTarget.value)
  if (!id || !target) return
  const ok = await confirmAsk(
    '같은 사람으로 합칠까요?',
    `${name.value}의 기록 ${recordCount.value}건을 ${target.name}${target.group ? `(${target.group})` : ''}에게 옮기고, 이 사람은 삭제해요.`,
    '합치기',
  )
  if (!ok) return
  await mergePeople(id, target.id)
  showToast('합쳤어요')
  router.replace(`/people/${target.id}`)
}

async function remove() {
  if (!id) return
  const ok = await confirmAsk('사람을 삭제할까요?', `이 사람의 기록 ${recordCount.value}건과 이 사람의 경조사도 함께 삭제돼요.`, '삭제')
  if (!ok) return
  await deletePerson(id)
  showToast('삭제했어요')
  router.replace('/people')
}
</script>

<template>
  <div class="page no-tab">
    <label class="label" for="pname">이름</label>
    <div class="row">
      <input id="pname" v-model="name" class="field grow" autocomplete="off" />
      <button v-if="contactsSupported && !id" type="button" class="btn sm secondary" @click="fromContacts">📇 연락처</button>
    </div>
    <RouterLink v-if="contactsSupported && !id" to="/contacts" class="small many">연락처에서 여러 명 한꺼번에 불러오기 ›</RouterLink>
    <span class="label">관계</span>
    <div class="chips">
      <button v-for="r in RELATIONS" :key="r.value" type="button" class="chip" :aria-pressed="relation === r.value" @click="relation = r.value">{{ r.label }}</button>
    </div>
    <label class="label" for="pgroup">소속·설명 <span class="muted small">(동명이인 구분용)</span></label>
    <input id="pgroup" v-model="group" class="field" placeholder="예: 대학 동기, ○○회사" />
    <label class="label" for="pmemo">메모</label>
    <textarea id="pmemo" v-model="memo" class="field" placeholder="예: 축의금 전달은 계좌로" />
    <button class="btn save" @click="save">저장</button>

    <template v-if="id">
      <h2 class="section-title">다른 사람과 합치기</h2>
      <div class="card">
        <p class="muted small">같은 사람이 둘로 나뉘어 있다면 하나로 합칠 수 있어요.</p>
        <select v-model="mergeTarget" class="field" aria-label="합칠 사람">
          <option value="">합칠 사람 고르기</option>
          <option v-for="p in others" :key="p.id" :value="p.id">{{ p.name }} · {{ relationLabel(p.relation) }}{{ p.group ? ` · ${p.group}` : '' }}</option>
        </select>
        <button class="btn secondary merge" :disabled="!mergeTarget" @click="merge">이 사람에게 합치기</button>
      </div>
      <button class="btn outline delete" @click="remove">사람 삭제</button>
    </template>
  </div>
</template>

<style scoped>
.save { margin-top: 20px; }
.many { display: inline-block; margin-top: 8px; }
.merge { margin-top: 10px; }
.delete { margin-top: 24px; }
</style>
