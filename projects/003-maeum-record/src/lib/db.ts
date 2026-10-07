import Dexie, { type Table } from 'dexie'
import type { Entry, Mood } from './mood'
import { nowTime, todayKey } from './date'

interface Setting {
  key: string
  value: unknown
}

class MaeumDB extends Dexie {
  entries!: Table<Entry, string>
  settings!: Table<Setting, string>

  constructor() {
    super('maeum-record')
    this.version(1).stores({
      entries: 'id, date',
      settings: 'key',
    })
  }
}

export const db = new MaeumDB()

const uuid = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`

export interface EntryInput {
  mood: Mood
  memo: string
  tags: string[]
  date?: string
  time?: string
}

export async function addEntry(input: EntryInput): Promise<Entry> {
  const now = Date.now()
  const entry: Entry = {
    id: uuid(),
    date: input.date ?? todayKey(),
    time: input.time ?? nowTime(),
    mood: input.mood,
    memo: input.memo.trim(),
    tags: [...input.tags],
    createdAt: now,
    updatedAt: now,
  }
  await db.entries.add(entry)
  return entry
}

export async function updateEntry(id: string, patch: Partial<Pick<Entry, 'mood' | 'memo' | 'tags' | 'time'>>) {
  await db.entries.update(id, { ...patch, updatedAt: Date.now() })
}

export const deleteEntry = (id: string) => db.entries.delete(id)

export const entriesOn = (date: string) => db.entries.where('date').equals(date).sortBy('time')

export const entriesBetween = (from: string, to: string) => db.entries.where('date').between(from, to, true, true).toArray()

export const allEntries = () => db.entries.toArray()

export async function getSetting<T>(key: string, fallback: T): Promise<T> {
  const row = await db.settings.get(key)
  return row === undefined ? fallback : (row.value as T)
}

export const setSetting = (key: string, value: unknown) => db.settings.put({ key, value })

export async function replaceAllEntries(entries: Entry[]) {
  await db.transaction('rw', db.entries, async () => {
    await db.entries.clear()
    await db.entries.bulkAdd(entries)
  })
}

export async function wipeAll() {
  await db.transaction('rw', db.entries, db.settings, async () => {
    await db.entries.clear()
    await db.settings.clear()
  })
}
