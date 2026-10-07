/**
 * 백업 파일 만들기·읽기·합치기 (순수 함수, 테스트 대상)
 * 형식: tech-stack.md 5-1 / 합치기 규칙: tech-stack.md 5-2
 */
import { decryptText, encryptText, type EncryptedPayload } from './crypto'
import { isDateKey } from './date'
import type { LedgerData, LedgerEvent, LedgerRecord, Person } from './types'

export const BACKUP_FORMAT = 'maeum-jangbu-backup'
export const BACKUP_VERSION = 1

interface BackupBase {
  format: typeof BACKUP_FORMAT
  version: number
  exportedAt: string
}
export interface PlainBackup extends BackupBase {
  encrypted: false
  data: LedgerData
}
export interface EncryptedBackup extends BackupBase, EncryptedPayload {
  encrypted: true
}
export type BackupFile = PlainBackup | EncryptedBackup

export async function makeBackupText(data: LedgerData, password?: string, now = new Date()): Promise<string> {
  const base = { format: BACKUP_FORMAT, version: BACKUP_VERSION, exportedAt: now.toISOString() } as const
  if (!password) return JSON.stringify({ ...base, encrypted: false, data } satisfies PlainBackup, null, 2)
  const payload = await encryptText(JSON.stringify(data), password)
  return JSON.stringify({ ...base, encrypted: true, ...payload } satisfies EncryptedBackup, null, 2)
}

/** 파일 내용을 읽어 형식만 확인한다. 암호화된 경우 데이터는 아직 풀지 않는다. */
export function readBackupFile(text: string): BackupFile {
  let d: Partial<BackupFile> & Record<string, unknown>
  try {
    d = JSON.parse(text)
  } catch {
    throw new Error('백업 파일을 읽을 수 없어요. 마음장부에서 만든 파일인지 확인해 주세요.')
  }
  if (d?.format !== BACKUP_FORMAT) throw new Error('마음장부 백업 파일이 아니에요.')
  if (typeof d.version !== 'number' || d.version > BACKUP_VERSION) {
    throw new Error('더 새로운 버전의 앱에서 만든 백업이에요. 앱을 업데이트한 뒤 다시 시도해 주세요.')
  }
  if (d.encrypted === true) {
    if (typeof d.data !== 'string' || !d.kdf || !d.cipher) throw new Error('백업 파일이 손상되었어요.')
    return d as EncryptedBackup
  }
  return { ...(d as PlainBackup), encrypted: false, data: sanitizeData(d.data) }
}

/** 암호화된 백업 풀기. 비밀번호가 틀리면 WrongPasswordError */
export async function openBackup(file: BackupFile, password?: string): Promise<LedgerData> {
  if (!file.encrypted) return file.data
  const text = await decryptText(file, password ?? '')
  try {
    return sanitizeData(JSON.parse(text))
  } catch {
    throw new Error('백업 파일이 손상되었어요.')
  }
}

const str = (v: unknown, fallback = '') => (typeof v === 'string' ? v : fallback)
const num = (v: unknown, fallback = Date.now()) => (typeof v === 'number' && Number.isFinite(v) ? v : fallback)
const oneOf = <T extends string>(v: unknown, values: readonly T[], fallback: T): T =>
  values.includes(v as T) ? (v as T) : fallback

/** 잘못된 항목은 버리고, 빠진 필드는 기본값으로 채운다 */
export function sanitizeData(raw: unknown): LedgerData {
  const d = (raw ?? {}) as Record<string, unknown>
  if (!Array.isArray(d.people) || !Array.isArray(d.events) || !Array.isArray(d.records)) {
    throw new Error('백업 파일이 손상되었어요.')
  }
  const people: Person[] = d.people
    .filter((p): p is Record<string, unknown> => !!p && typeof p.id === 'string' && typeof p.name === 'string')
    .map((p) => ({
      id: p.id as string,
      name: (p.name as string).trim(),
      relation: oneOf(p.relation, ['family', 'relative', 'friend', 'work', 'acquaintance', 'other'] as const, 'other'),
      group: str(p.group),
      memo: str(p.memo),
      createdAt: num(p.createdAt),
      updatedAt: num(p.updatedAt),
    }))
  const personIds = new Set(people.map((p) => p.id))
  const events: LedgerEvent[] = d.events
    .filter((e): e is Record<string, unknown> => !!e && typeof e.id === 'string' && isDateKey(e.date))
    .map((e) => ({
      id: e.id as string,
      owner: oneOf(e.owner, ['mine', 'theirs'] as const, 'mine'),
      personId: typeof e.personId === 'string' && personIds.has(e.personId) ? e.personId : null,
      type: oneOf(e.type, ['wedding', 'funeral', 'firstBirthday', 'birthday', 'opening', 'other'] as const, 'other'),
      title: str(e.title, '경조사'),
      date: e.date as string,
      place: str(e.place),
      remind: e.remind === true,
      noRecordNeeded: e.noRecordNeeded === true,
      createdAt: num(e.createdAt),
      updatedAt: num(e.updatedAt),
    }))
  const eventIds = new Set(events.map((e) => e.id))
  const records: LedgerRecord[] = d.records
    .filter(
      (r): r is Record<string, unknown> =>
        !!r && typeof r.id === 'string' && personIds.has(r.personId as string) && eventIds.has(r.eventId as string),
    )
    .map((r) => ({
      id: r.id as string,
      eventId: r.eventId as string,
      personId: r.personId as string,
      direction: oneOf(r.direction, ['received', 'given'] as const, 'received'),
      amount: Math.max(0, Math.round(num(r.amount, 0))),
      method: oneOf(r.method, ['cash', 'transfer', 'flower', 'gift', 'other'] as const, 'cash'),
      attended: typeof r.attended === 'boolean' ? r.attended : null,
      thanked: r.thanked === true,
      memo: str(r.memo),
      source: oneOf(r.source, ['manual', 'ocr', 'import'] as const, 'manual'),
      createdAt: num(r.createdAt),
      updatedAt: num(r.updatedAt),
    }))
  return { people, events, records }
}

export interface NameConflict {
  existing: Person
  incoming: Person
}

/**
 * 이름은 같지만 id가 다른 사람 (tech-stack.md 5-2).
 * 자동으로 합치지 않고 사용자에게 "같은 사람인가요?"를 묻는다.
 */
export function findNameConflicts(existing: LedgerData, incoming: LedgerData): NameConflict[] {
  const ids = new Set(existing.people.map((p) => p.id))
  const out: NameConflict[] = []
  for (const p of incoming.people) {
    if (ids.has(p.id)) continue
    const same = existing.people.find((e) => e.name === p.name)
    if (same) out.push({ existing: same, incoming: p })
  }
  return out
}

export interface MergeResult {
  result: LedgerData
  added: { people: number; events: number; records: number }
  skippedRecords: number
}

/**
 * 합치기. sameAs: 사용자가 "같은 사람"이라고 답한 쌍 (incoming id → existing id)
 * - 사람: id가 같으면 같은 사람. sameAs에 있으면 기존 사람으로 연결.
 * - 행사: id가 같거나, owner + type + date + 대상 사람이 같으면 같은 행사.
 * - 내역: id가 같거나, 행사 + 사람 + 받음/보냄 + 금액이 같으면 중복으로 건너뜀.
 */
export function mergeData(existing: LedgerData, incoming: LedgerData, sameAs: Record<string, string> = {}): MergeResult {
  const people = [...existing.people]
  const events = [...existing.events]
  const records = [...existing.records]
  const added = { people: 0, events: 0, records: 0 }

  const personMap = new Map<string, string>()
  const personIds = new Set(people.map((p) => p.id))
  for (const p of incoming.people) {
    if (personIds.has(p.id)) personMap.set(p.id, p.id)
    else if (sameAs[p.id] && personIds.has(sameAs[p.id])) personMap.set(p.id, sameAs[p.id])
    else {
      people.push(p)
      personIds.add(p.id)
      personMap.set(p.id, p.id)
      added.people++
    }
  }

  const eventKey = (e: LedgerEvent) => `${e.owner}|${e.type}|${e.date}|${e.personId ?? ''}`
  const eventById = new Map(events.map((e) => [e.id, e]))
  const eventByKey = new Map(events.map((e) => [eventKey(e), e]))
  const eventMap = new Map<string, string>()
  for (const raw of incoming.events) {
    const e = { ...raw, personId: raw.personId ? (personMap.get(raw.personId) ?? null) : null }
    const found = eventById.get(e.id) ?? eventByKey.get(eventKey(e))
    if (found) eventMap.set(e.id, found.id)
    else {
      events.push(e)
      eventById.set(e.id, e)
      eventByKey.set(eventKey(e), e)
      eventMap.set(e.id, e.id)
      added.events++
    }
  }

  const recordKey = (r: LedgerRecord) => `${r.eventId}|${r.personId}|${r.direction}|${r.amount}`
  const recordIds = new Set(records.map((r) => r.id))
  const recordKeys = new Set(records.map(recordKey))
  let skippedRecords = 0
  for (const raw of incoming.records) {
    const personId = personMap.get(raw.personId)
    const eventId = eventMap.get(raw.eventId)
    if (!personId || !eventId) { skippedRecords++; continue }
    const r = { ...raw, personId, eventId }
    if (recordIds.has(r.id) || recordKeys.has(recordKey(r))) { skippedRecords++; continue }
    records.push(r)
    recordIds.add(r.id)
    recordKeys.add(recordKey(r))
    added.records++
  }

  return { result: { people, events, records }, added, skippedRecords }
}

export interface BackupPreview {
  people: number
  events: number
  records: number
  from: string | null
  to: string | null
}

export function previewOf(data: LedgerData): BackupPreview {
  const dates = data.events.map((e) => e.date).sort()
  return {
    people: data.people.length,
    events: data.events.length,
    records: data.records.length,
    from: dates[0] ?? null,
    to: dates[dates.length - 1] ?? null,
  }
}

export const backupFileName = (dateKey: string) => `마음장부_백업_${dateKey}.json`

/** 백업 알림 기준 (idea.md 3-3, 2026-10-07 결정) */
export const BACKUP_REMINDER_DAYS = 30
const DAY = 86_400_000

export type BackupStatus =
  | { kind: 'empty' }
  | { kind: 'never'; changes: number }
  | { kind: 'overdue'; days: number; changes: number }
  | { kind: 'ok'; lastAt: number; changes: number }

/**
 * 홈 백업 카드 상태 (screens.md S-02)
 * - 기록 없음 → 숨김
 * - 백업한 적 없음 → 강조
 * - 마지막 백업 후 30일 이상 + 그 사이 바뀐 기록 있음 → ⚠
 */
export function backupStatus(
  hasData: boolean,
  lastBackupAt: number | null,
  changesSinceBackup: number,
  now = Date.now(),
  reminderDays = BACKUP_REMINDER_DAYS,
): BackupStatus {
  if (!hasData) return { kind: 'empty' }
  if (lastBackupAt === null) return { kind: 'never', changes: changesSinceBackup }
  const days = Math.floor((now - lastBackupAt) / DAY)
  if (days >= reminderDays && changesSinceBackup > 0) return { kind: 'overdue', days, changes: changesSinceBackup }
  return { kind: 'ok', lastAt: lastBackupAt, changes: changesSinceBackup }
}
