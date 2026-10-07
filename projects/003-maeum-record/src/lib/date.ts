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

export function todayKey(now = new Date()): string {
  return toKey(now)
}

export function nowTime(now = new Date()): string {
  return `${pad(now.getHours())}:${pad(now.getMinutes())}`
}

export function addDays(key: string, n: number): string {
  const d = fromKey(key)
  d.setDate(d.getDate() + n)
  return toKey(d)
}

/** from ~ to (양 끝 포함) 날짜 목록 */
export function dateRange(from: string, to: string): string[] {
  const out: string[] = []
  for (let k = from; k <= to; k = addDays(k, 1)) out.push(k)
  return out
}

/** 10월 7일 수요일 */
export function formatLong(key: string): string {
  const d = fromKey(key)
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${WEEKDAYS[d.getDay()]}요일`
}

/** 10/7 */
export function formatShort(key: string): string {
  const d = fromKey(key)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 2026.10.07 */
export function formatDot(key: string): string {
  return key.replaceAll('-', '.')
}

/** 오후 2:10 */
export function formatTime(time: string): string {
  const [h, m] = time.split(':').map(Number)
  const ampm = h < 12 ? '오전' : '오후'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${ampm} ${h12}:${pad(m)}`
}

/** 달력용: 해당 월의 칸 (앞쪽 빈칸은 null) */
export function monthCells(year: number, month0: number): (string | null)[] {
  const first = new Date(year, month0, 1)
  const days = new Date(year, month0 + 1, 0).getDate()
  const cells: (string | null)[] = Array(first.getDay()).fill(null)
  for (let d = 1; d <= days; d++) cells.push(toKey(new Date(year, month0, d)))
  return cells
}

export { WEEKDAYS }
