const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

const pad = (n: number) => String(n).padStart(2, '0')

/** 기기 시간대 기준 YYYY-MM-DD */
export function toKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function fromKey(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const todayKey = (now = new Date()) => toKey(now)

export function addDays(key: string, n: number): string {
  const d = fromKey(key)
  d.setDate(d.getDate() + n)
  return toKey(d)
}

/** to - from (일) */
export function daysBetween(from: string, to: string): number {
  const a = fromKey(from)
  const b = fromKey(to)
  return Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / 86400000)
}

/** D-3, D-day, D+2 */
export function ddayLabel(date: string, today: string): string {
  const n = daysBetween(today, date)
  if (n === 0) return 'D-day'
  return n > 0 ? `D-${n}` : `D+${-n}`
}

/** 11/21(토) */
export function formatShortDay(key: string): string {
  const d = fromKey(key)
  return `${d.getMonth() + 1}/${d.getDate()}(${WEEKDAYS[d.getDay()]})`
}

/** 10/05 */
export function formatMD(key: string): string {
  return `${key.slice(5, 7)}/${key.slice(8, 10)}`
}

/** 2026.10.07 */
export const formatDot = (key: string) => key.replaceAll('-', '.')

export const isDateKey = (s: unknown): s is string => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s)
