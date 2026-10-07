import { computed, shallowRef } from 'vue'
import { CHANGED_EVENT, loadAll } from './db'
import type { LedgerData } from './types'

/**
 * 화면에서 쓰는 장부 데이터. 기록이 바뀌면(CHANGED_EVENT) 다시 읽는다.
 * 수천 건 규모라 전체를 메모리에 두고 계산한다 (tech-stack.md 2장: 합계는 매번 계산).
 */
export const ledger = shallowRef<LedgerData>({ people: [], events: [], records: [] })
export const loaded = shallowRef(false)

export async function reload() {
  ledger.value = await loadAll()
  loaded.value = true
}

if (typeof window !== 'undefined') window.addEventListener(CHANGED_EVENT, () => void reload())

export const peopleById = computed(() => new Map(ledger.value.people.map((p) => [p.id, p])))
export const eventsById = computed(() => new Map(ledger.value.events.map((e) => [e.id, e])))
