import type { Entry } from './mood'
import { dateRange } from './date'

export interface Summary {
  from: string
  to: string
  totalDays: number
  recordedDays: number
  /** index 0 = 아주 힘듦(1) ... index 4 = 좋음(5). 기록 건수가 아닌 "날" 기준 (그날 평균) */
  distribution: [number, number, number, number, number]
  daily: { date: string; avg: number | null }[]
  topTags: { tag: string; count: number }[]
  memos: { date: string; time: string; memo: string }[]
}

/** 하루 기록들의 평균 기분을 반올림한 값 (screens.md S-03) */
export function dayMood(entries: Entry[]): number | null {
  if (entries.length === 0) return null
  const avg = entries.reduce((s, e) => s + e.mood, 0) / entries.length
  return Math.round(avg)
}

export function groupByDate(entries: Entry[]): Map<string, Entry[]> {
  const map = new Map<string, Entry[]>()
  for (const e of entries) {
    const list = map.get(e.date)
    if (list) list.push(e)
    else map.set(e.date, [e])
  }
  for (const list of map.values()) list.sort((a, b) => a.time.localeCompare(b.time))
  return map
}

/**
 * 진료 준비(S-04)·리포트(S-05)용 요약. 해석이나 점수는 만들지 않는다.
 */
export function summarize(entries: Entry[], from: string, to: string, memoLimit = 5): Summary {
  const inRange = entries.filter((e) => e.date >= from && e.date <= to)
  const byDate = groupByDate(inRange)
  const days = dateRange(from, to)

  const distribution: Summary['distribution'] = [0, 0, 0, 0, 0]
  const daily = days.map((date) => {
    const list = byDate.get(date) ?? []
    const m = dayMood(list)
    if (m !== null) distribution[m - 1]++
    const avg = list.length ? list.reduce((s, e) => s + e.mood, 0) / list.length : null
    return { date, avg }
  })

  const tagCount = new Map<string, number>()
  for (const e of inRange) for (const t of e.tags) tagCount.set(t, (tagCount.get(t) ?? 0) + 1)
  const topTags = [...tagCount.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
    .slice(0, 3)

  const memos = inRange
    .filter((e) => e.memo.trim())
    .sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time))
    .slice(0, memoLimit)
    .map((e) => ({ date: e.date, time: e.time, memo: e.memo.trim() }))

  return {
    from,
    to,
    totalDays: days.length,
    recordedDays: byDate.size,
    distribution,
    daily,
    topTags,
    memos,
  }
}
