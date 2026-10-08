import Dexie, { type Table } from 'dexie'
import { uuid, type LedgerData, type LedgerEvent, type LedgerRecord, type Person } from './types'

interface Setting {
  key: string
  value: unknown
}

class JangbuDB extends Dexie {
  people!: Table<Person, string>
  events!: Table<LedgerEvent, string>
  records!: Table<LedgerRecord, string>
  settings!: Table<Setting, string>

  constructor() {
    super('maeum-jangbu')
    this.version(1).stores({
      people: 'id, name',
      events: 'id, date, owner, personId',
      records: 'id, eventId, personId, direction',
      settings: 'key',
    })
  }
}

export const db = new JangbuDB()

export async function getSetting<T>(key: string, fallback: T): Promise<T> {
  const row = await db.settings.get(key)
  return row === undefined ? fallback : (row.value as T)
}

export const setSetting = (key: string, value: unknown) => db.settings.put({ key, value })

export const CHANGED_EVENT = 'ledger-changed'

/** 기록이 바뀔 때마다: 백업 이후 변경 건수 증가 + 화면·알림 갱신 신호 */
async function changed(n = 1) {
  const changes = await getSetting('changesSinceBackup', 0)
  if (changes === 0) await setSetting('pendingSince', Date.now())
  await setSetting('changesSinceBackup', changes + n)
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CHANGED_EVENT))
}

export async function markBackedUp(now = Date.now()) {
  await setSetting('lastBackupAt', now)
  await setSetting('changesSinceBackup', 0)
  await setSetting('pendingSince', null)
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CHANGED_EVENT))
}

export async function loadAll(): Promise<LedgerData> {
  const [people, events, records] = await Promise.all([db.people.toArray(), db.events.toArray(), db.records.toArray()])
  return { people, events, records }
}

type New<T> = Omit<T, 'id' | 'createdAt' | 'updatedAt'>

export async function addPerson(input: New<Person>): Promise<Person> {
  const now = Date.now()
  const p: Person = { ...input, name: input.name.trim(), group: input.group.trim(), id: uuid(), createdAt: now, updatedAt: now }
  await db.people.add(p)
  await changed()
  return p
}

/** 여러 명 한 번에 추가 (연락처 불러오기). 변경 건수는 추가한 사람 수만큼 */
export async function addPeople(inputs: New<Person>[]): Promise<number> {
  if (!inputs.length) return 0
  const now = Date.now()
  await db.people.bulkAdd(
    inputs.map((p, i) => ({ ...p, name: p.name.trim(), group: p.group.trim(), id: uuid(), createdAt: now + i, updatedAt: now + i })),
  )
  await changed(inputs.length)
  return inputs.length
}

export async function updatePerson(id: string, patch: Partial<New<Person>>) {
  await db.people.update(id, { ...patch, updatedAt: Date.now() })
  await changed()
}

/** 사람 삭제: 그 사람의 내역과, 그 사람의 상대 행사(와 내역)도 함께 삭제 */
export async function deletePerson(id: string) {
  await db.transaction('rw', db.people, db.events, db.records, async () => {
    const theirEvents = await db.events.where('personId').equals(id).primaryKeys()
    await db.records.where('personId').equals(id).delete()
    await db.records.where('eventId').anyOf(theirEvents).delete()
    await db.events.bulkDelete(theirEvents)
    await db.people.delete(id)
  })
  await changed()
}

/** 여러 사람의 관계를 한꺼번에 바꾸기 (사람 목록 → 선택). 바꾼 사람 수를 돌려준다 */
export async function setRelation(ids: string[], relation: Person['relation']): Promise<number> {
  if (!ids.length) return 0
  const now = Date.now()
  const n = await db.people.where('id').anyOf(ids).modify({ relation, updatedAt: now })
  await changed(n || 1)
  return n
}

/** 동명이인으로 잘못 나뉜 사람 합치기 (screens.md S-04): from의 기록을 into로 옮기고 from 삭제 */
export async function mergePeople(fromId: string, intoId: string) {
  if (fromId === intoId) return
  await db.transaction('rw', db.people, db.events, db.records, async () => {
    await db.records.where('personId').equals(fromId).modify({ personId: intoId, updatedAt: Date.now() })
    await db.events.where('personId').equals(fromId).modify({ personId: intoId, updatedAt: Date.now() })
    await db.people.delete(fromId)
  })
  await changed()
}

export async function addEvent(input: New<LedgerEvent>): Promise<LedgerEvent> {
  const now = Date.now()
  const e: LedgerEvent = { ...input, title: input.title.trim(), id: uuid(), createdAt: now, updatedAt: now }
  await db.events.add(e)
  await changed()
  return e
}

export async function updateEvent(id: string, patch: Partial<New<LedgerEvent>>) {
  await db.events.update(id, { ...patch, updatedAt: Date.now() })
  await changed()
}

export async function deleteEvent(id: string) {
  await db.transaction('rw', db.events, db.records, async () => {
    await db.records.where('eventId').equals(id).delete()
    await db.events.delete(id)
  })
  await changed()
}

export async function addRecord(input: New<LedgerRecord>): Promise<LedgerRecord> {
  const now = Date.now()
  const r: LedgerRecord = { ...input, memo: input.memo.trim(), id: uuid(), createdAt: now, updatedAt: now }
  await db.records.add(r)
  await changed()
  return r
}

export async function updateRecord(id: string, patch: Partial<New<LedgerRecord>>) {
  await db.records.update(id, { ...patch, updatedAt: Date.now() })
  await changed()
}

export async function deleteRecord(id: string) {
  await db.records.delete(id)
  await changed()
}

export async function replaceAll(data: LedgerData) {
  await db.transaction('rw', db.people, db.events, db.records, async () => {
    await Promise.all([db.people.clear(), db.events.clear(), db.records.clear()])
    await db.people.bulkAdd(data.people)
    await db.events.bulkAdd(data.events)
    await db.records.bulkAdd(data.records)
  })
  await changed(data.records.length || 1)
}

export async function wipeAll() {
  await db.transaction('rw', [db.people, db.events, db.records, db.settings], async () => {
    await Promise.all([db.people.clear(), db.events.clear(), db.records.clear(), db.settings.clear()])
  })
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CHANGED_EVENT))
}
