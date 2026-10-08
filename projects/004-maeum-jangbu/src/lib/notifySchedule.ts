/**
 * 알림 일정 계산 (순수 함수, 테스트 대상)
 * - 경조사 D-day 알림: 상대 행사 중 알림을 켠 행사, 정한 날짜·시각에 1번 (screens.md S-13)
 * - 백업 알림: 마지막 백업 후 30일, 그 사이 기록이 바뀐 경우만 (idea.md 3-3)
 * 앱을 열 때·기록을 바꿀 때마다 다시 계산한다.
 */
import type { LedgerEvent } from './types'
import { fromKey, formatShortDay, toKey } from './date'

export const EVENT_ID_BASE = 2000
export const EVENT_MAX = 50
export const BACKUP_ID = 3000
const DAY = 86_400_000

export interface NotifySettings {
  eventEnabled: boolean
  /** 0 = 당일, 1 = 하루 전 ... */
  daysBefore: number
  /** HH:mm */
  time: string
  backupEnabled: boolean
  backupDays: number
}

export const DEFAULT_NOTIFY: NotifySettings = { eventEnabled: true, daysBefore: 1, time: '09:00', backupEnabled: true, backupDays: 30 }

export interface BackupState {
  lastBackupAt: number | null
  /** 백업 이후 처음 기록이 바뀐 시각 */
  pendingSince: number | null
  changes: number
}

export interface PlannedNotification {
  id: number
  at: Date
  title: string
  body: string
  route: string
}

export function parseTime(time: string): { hour: number; minute: number } {
  const m = /^(\d{1,2}):(\d{2})$/.exec(time)
  if (!m || Number(m[1]) > 23 || Number(m[2]) > 59) return { hour: 9, minute: 0 }
  return { hour: Number(m[1]), minute: Number(m[2]) }
}

const whenLabel = (daysBefore: number) => (daysBefore === 0 ? '오늘' : daysBefore === 1 ? '내일' : `${daysBefore}일 뒤`)

export function planNotifications(now: Date, events: LedgerEvent[], s: NotifySettings, backup: BackupState): PlannedNotification[] {
  const out: PlannedNotification[] = []
  const { hour, minute } = parseTime(s.time)
  const today = toKey(now)

  if (s.eventEnabled) {
    const upcoming = events
      .filter((e) => e.owner === 'theirs' && e.remind && e.date >= today)
      .sort((a, b) => a.date.localeCompare(b.date))
    for (const e of upcoming) {
      if (out.length >= EVENT_MAX) break
      const d = fromKey(e.date)
      const at = new Date(d.getFullYear(), d.getMonth(), d.getDate() - s.daysBefore, hour, minute)
      if (at.getTime() <= now.getTime()) continue
      out.push({
        id: EVENT_ID_BASE + out.length,
        at,
        title: `${whenLabel(s.daysBefore)} ${e.title}`,
        body: `${formatShortDay(e.date)}${e.place ? ` · ${e.place}` : ''}`,
        route: `/events/${e.id}`,
      })
    }
  }

  if (s.backupEnabled && backup.changes > 0) {
    const base = backup.lastBackupAt ?? backup.pendingSince ?? now.getTime()
    let at = new Date(base + s.backupDays * DAY)
    // 이미 지났으면 사흘 뒤 한 번 (앱을 열 때마다 매일 울리지 않게)
    if (at.getTime() <= now.getTime()) at = new Date(now.getTime() + 3 * DAY)
    at = new Date(at.getFullYear(), at.getMonth(), at.getDate(), 20, 0)
    out.push({
      id: BACKUP_ID,
      at,
      title: backup.lastBackupAt === null ? '아직 백업하지 않았어요' : `마지막 백업 후 ${s.backupDays}일이 지났어요`,
      body: '휴대폰을 바꾸거나 앱을 지우면 기록이 사라져요. 백업해 두세요.',
      route: '/backup',
    })
  }
  return out
}

/** 이전에 예약했을 수 있는 모든 알림 id (취소용) */
export const allNotificationIds = () => [...Array.from({ length: EVENT_MAX }, (_, i) => EVENT_ID_BASE + i), BACKUP_ID]
