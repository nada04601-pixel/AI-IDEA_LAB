import type { Entry } from './mood'

export const BACKUP_FORMAT = 'maeum-record-backup'
export const BACKUP_VERSION = 1

export interface BackupFile {
  format: typeof BACKUP_FORMAT
  version: number
  exportedAt: string
  entries: Entry[]
  visitNote?: string
}

export function makeBackup(entries: Entry[], visitNote: string, now = new Date()): BackupFile {
  return { format: BACKUP_FORMAT, version: BACKUP_VERSION, exportedAt: now.toISOString(), entries, visitNote }
}

const isEntry = (v: unknown): v is Entry => {
  if (!v || typeof v !== 'object') return false
  const e = v as Record<string, unknown>
  return (
    typeof e.id === 'string' &&
    typeof e.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(e.date) &&
    typeof e.time === 'string' && /^\d{2}:\d{2}$/.test(e.time) &&
    typeof e.mood === 'number' && [1, 2, 3, 4, 5].includes(e.mood) &&
    typeof e.memo === 'string' &&
    Array.isArray(e.tags) && e.tags.every((t) => typeof t === 'string')
  )
}

/** 백업 파일 내용을 검사한다. 잘못된 파일이면 사용자에게 보여줄 이유와 함께 예외. */
export function parseBackup(text: string): BackupFile {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('백업 파일을 읽을 수 없어요. 마음기록에서 만든 파일인지 확인해 주세요.')
  }
  const d = data as Partial<BackupFile>
  if (d?.format !== BACKUP_FORMAT || !Array.isArray(d.entries)) {
    throw new Error('마음기록 백업 파일이 아니에요.')
  }
  const entries = d.entries.filter(isEntry).map((e) => ({
    ...e,
    createdAt: typeof e.createdAt === 'number' ? e.createdAt : Date.now(),
    updatedAt: typeof e.updatedAt === 'number' ? e.updatedAt : Date.now(),
  }))
  return { ...(d as BackupFile), entries }
}

const sameRecord = (a: Entry, b: Entry) => a.date === b.date && a.time === b.time && a.mood === b.mood

/**
 * screens.md S-09: 합치기 / 덮어쓰기.
 * 합치기는 id가 같거나, 날짜·시각·기분이 같은 기록을 중복으로 보고 건너뛴다.
 */
export function mergeEntries(existing: Entry[], incoming: Entry[], mode: 'merge' | 'replace'): { result: Entry[]; added: number; skipped: number } {
  if (mode === 'replace') return { result: [...incoming], added: incoming.length, skipped: 0 }
  const result = [...existing]
  const ids = new Set(existing.map((e) => e.id))
  let added = 0
  let skipped = 0
  for (const e of incoming) {
    if (ids.has(e.id) || result.some((r) => sameRecord(r, e))) {
      skipped++
      continue
    }
    result.push(e)
    ids.add(e.id)
    added++
  }
  return { result, added, skipped }
}

export function backupFileName(dateKey: string) {
  return `마음기록_백업_${dateKey}.json`
}

export const BACKUP_NUDGE_DAYS = 30

/**
 * 백업 권유 (idea.md 6-5). 마지막 백업(없으면 첫 기록) 후 30일이 지나면 경과 일수를 돌려준다.
 * 기록이 없으면 권유하지 않는다. 독촉 알림은 보내지 않고, 화면에 조용히 한 줄만 보여준다.
 */
export function backupNudgeDays(lastBackupAt: number | null, oldestEntryDate: string | null, now = new Date()): number | null {
  if (!oldestEntryDate) return null
  const since = lastBackupAt !== null ? new Date(lastBackupAt) : (() => {
    const [y, m, d] = oldestEntryDate.split('-').map(Number)
    return new Date(y, m - 1, d)
  })()
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(since)) / 86_400_000)
  return days >= BACKUP_NUDGE_DAYS ? days : null
}

/** 설정 화면용: "오늘", "3일 전", "아직 없음" */
export function lastBackupLabel(lastBackupAt: number | null, now = new Date()): string {
  if (lastBackupAt === null) return '아직 없음'
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(new Date(lastBackupAt))) / 86_400_000)
  return days <= 0 ? '오늘' : `${days}일 전`
}
