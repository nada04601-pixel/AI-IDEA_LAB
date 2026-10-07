<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { ledger } from '../lib/store'
import { addPeople } from '../lib/db'
import { ContactsDeniedError, contactsSupported, listContacts } from '../lib/contacts'
import { contactRows, filterRows, toPeopleInput, type ContactRow } from '../lib/contactsImport'
import { RELATIONS, type Relation } from '../lib/types'
import { showToast } from '../lib/toast'

/** 연락처에서 여러 명 불러오기 (S-03 사람 추가). 이름·회사명만, 전화번호는 가져오지 않는다 */
const router = useRouter()
const rows = shallowRef<ContactRow[] | null>(null)
const selected = ref(new Set<string>())
const q = ref('')
const relation = ref<Relation>('friend')
const orgAsGroup = ref(true)
const busy = ref(false)
const error = ref<string | null>(null)

const shown = computed(() => (rows.value ? filterRows(rows.value, q.value) : []))
const allShownSelected = computed(() => shown.value.length > 0 && shown.value.every((r) => r.exists || selected.value.has(r.contact.id)))

async function load() {
  busy.value = true
  error.value = null
  try {
    rows.value = contactRows(await listContacts(), ledger.value.people)
  } catch (e) {
    error.value = e instanceof ContactsDeniedError ? e.message : `연락처를 읽지 못했어요. (${(e as Error).message})`
  } finally {
    busy.value = false
  }
}

function toggle(id: string) {
  const s = new Set(selected.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selected.value = s
}

function toggleAllShown() {
  const s = new Set(selected.value)
  const on = !allShownSelected.value
  for (const r of shown.value) if (!r.exists) (on ? s.add(r.contact.id) : s.delete(r.contact.id))
  selected.value = s
}

async function add() {
  if (!rows.value || !selected.value.size) return
  busy.value = true
  try {
    const n = await addPeople(toPeopleInput(rows.value, selected.value, relation.value, orgAsGroup.value))
    showToast(`${n}명을 추가했어요`)
    router.replace('/people')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page no-tab">
    <div v-if="!contactsSupported" class="card empty">
      <p><strong>안드로이드 앱에서 쓸 수 있어요</strong></p>
      <p class="muted">웹 버전에서는 휴대폰 연락처를 읽을 수 없어요.</p>
    </div>

    <template v-else-if="!rows">
      <div class="card intro">
        <h2>연락처에서 사람 불러오기</h2>
        <ul class="muted small">
          <li>이름과 회사명만 가져와요. <strong>전화번호는 가져오지 않아요.</strong></li>
          <li>고른 사람만 장부에 추가돼요. 연락처는 바뀌지 않아요.</li>
          <li>연락처 읽기 권한을 물어보면 허용해 주세요. 인터넷으로 보내지 않아요.</li>
        </ul>
        <button class="btn" :disabled="busy" @click="load">{{ busy ? '불러오는 중…' : '연락처 불러오기' }}</button>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p class="muted small tip">한 명만 필요하면 기록할 때 이름 칸 옆 📇 버튼을 누르세요. 이때는 권한이 필요 없어요.</p>
    </template>

    <template v-else>
      <input v-model="q" class="field" type="search" placeholder="이름·회사 검색" aria-label="연락처 검색" />
      <div class="between bar">
        <span class="muted small">연락처 {{ rows.length }}명 · {{ selected.size }}명 선택</span>
        <button class="chip" @click="toggleAllShown">{{ allShownSelected ? '선택 해제' : q ? '검색 결과 모두 선택' : '모두 선택' }}</button>
      </div>

      <div v-if="shown.length" class="card flush list-box">
        <ul class="list">
          <li v-for="r in shown" :key="r.contact.id">
            <label class="list-row pick" :class="{ dim: r.exists }">
              <input type="checkbox" :checked="selected.has(r.contact.id)" :disabled="r.exists" @change="toggle(r.contact.id)" />
              <span class="grow"><strong>{{ r.contact.name }}</strong><span v-if="r.contact.org" class="muted small rel">{{ r.contact.org }}</span></span>
              <span v-if="r.exists" class="badge">이미 있음</span>
            </label>
          </li>
        </ul>
      </div>
      <p v-else class="muted">찾는 연락처가 없어요.</p>

      <div class="card opts">
        <span class="label">고른 사람의 관계</span>
        <div class="chips">
          <button v-for="x in RELATIONS" :key="x.value" type="button" class="chip" :aria-pressed="relation === x.value" @click="relation = x.value">{{ x.label }}</button>
        </div>
        <label class="row small org"><input v-model="orgAsGroup" type="checkbox" /> 회사명을 소속으로 넣기</label>
        <p class="muted small">관계는 나중에 사람마다 바꿀 수 있어요.</p>
      </div>

      <button class="btn add" :disabled="busy || !selected.size" @click="add">{{ selected.size ? `${selected.size}명 추가` : '추가할 사람을 골라 주세요' }}</button>
    </template>
  </div>
</template>

<style scoped>
.intro h2 { margin-bottom: 6px; }
.intro ul { padding-left: 18px; margin: 0 0 14px; }
.intro li { margin-bottom: 4px; }
.error { color: var(--warn); background: var(--warn-soft); padding: 10px 12px; border-radius: 10px; margin-top: 12px; }
.tip { margin: 14px 4px; }
.bar { margin: 10px 2px; }
.list-box { max-height: 52vh; overflow-y: auto; }
.pick { cursor: pointer; padding: 11px 16px; }
.pick input { width: 20px; height: 20px; flex: none; }
.dim { opacity: 0.55; }
.opts { margin-top: 12px; }
.org { margin-top: 12px; }
.org input { width: 18px; height: 18px; }
.opts p { margin: 6px 0 0; }
.add { margin-top: 14px; }
</style>
