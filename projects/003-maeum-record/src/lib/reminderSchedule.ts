/**
 * 기록 알림 일정 계산 (순수 함수, 테스트 대상).
 *
 * 규칙 (screens.md S-09, idea.md 3. 핵심 설계 원칙)
 * - 하루 1회, 사용자가 정한 시각에만 보낸다.
 * - 오늘 이미 기록했으면 오늘 알림은 보내지 않는다.
 * - 기록을 안 해도 같은 날 다시 보내지 않는다 (독촉 없음).
 * - 앱을 열 때·기록할 때마다 다시 계산한다. 앱을 오래 열지 않으면 DAYS_AHEAD일 뒤 알림이 자연스럽게 멈춘다.
 */
export const DAYS_AHEAD = 30
export const ID_BASE = 1000

export const REMINDER_TITLE = '마음기록'
export const REMINDER_BODY = '오늘 기분, 남겨볼까요?'

export interface PlannedReminder {
  id: number
  at: Date
}

export function parseTime(time: string): { hour: number; minute: number } {
  const m = /^(\d{1,2}):(\d{2})$/.exec(time)
  if (!m) throw new Error(`잘못된 시각: ${time}`)
  const hour = Number(m[1])
  const minute = Number(m[2])
  if (hour > 23 || minute > 59) throw new Error(`잘못된 시각: ${time}`)
  return { hour, minute }
}

export function planReminders(now: Date, time: string, recordedToday: boolean, days = DAYS_AHEAD): PlannedReminder[] {
  const { hour, minute } = parseTime(time)
  const out: PlannedReminder[] = []
  for (let i = 0; i < days; i++) {
    const at = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i, hour, minute, 0, 0)
    if (i === 0 && (recordedToday || at.getTime() <= now.getTime())) continue
    out.push({ id: ID_BASE + i, at })
  }
  return out
}

/** 이전에 예약했을 수 있는 모든 알림 id (취소용) */
export const allReminderIds = (days = DAYS_AHEAD) => Array.from({ length: days }, (_, i) => ID_BASE + i)

export const DEFAULT_REMINDER_TIME = '21:00'
