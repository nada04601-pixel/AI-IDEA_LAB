/**
 * 장부 계산 (순수 함수, 테스트 대상)
 * 합계·차이·기록 참고는 저장하지 않고 매번 계산한다 (tech-stack.md 2장).
 */
import type { LedgerEvent, LedgerRecord, Method, Person } from './types'
import { formatSentence, formatShort } from './money'
import { daysBetween } from './date'

export interface Totals {
  received: number
  given: number
  receivedCount: number
  givenCount: number
}

const emptyTotals = (): Totals => ({ received: 0, given: 0, receivedCount: 0, givenCount: 0 })

export function totalsOf(records: LedgerRecord[]): Totals {
  const t = emptyTotals()
  for (const r of records) {
    if (r.direction === 'received') { t.received += r.amount; t.receivedCount++ } else { t.given += r.amount; t.givenCount++ }
  }
  return t
}

/** 사람별 합계 */
export function totalsByPerson(records: LedgerRecord[]): Map<string, Totals> {
  const map = new Map<string, Totals>()
  for (const r of records) {
    const t = map.get(r.personId) ?? emptyTotals()
    if (r.direction === 'received') { t.received += r.amount; t.receivedCount++ } else { t.given += r.amount; t.givenCount++ }
    map.set(r.personId, t)
  }
  return map
}

/** 차이 문구 (screens.md 4-3). 받음/보냄 기록이 하나도 없으면 null */
export function diffText(t: Totals): string | null {
  if (t.receivedCount + t.givenCount === 0) return null
  const d = t.received - t.given
  if (d === 0) return '주고받은 금액이 같아요'
  return d > 0 ? `받은 게 ${formatSentence(d)} 더 많아요` : `보낸 게 ${formatSentence(-d)} 더 많아요`
}

/** 목록용 짧은 차이: "받은 게 5만 더" */
export function diffShort(t: Totals): string | null {
  const d = t.received - t.given
  if (d === 0 || t.receivedCount + t.givenCount === 0) return null
  return d > 0 ? `받은 게 ${formatShort(d)} 더` : `보낸 게 ${formatShort(-d)} 더`
}

export interface EventSummary {
  count: number
  total: number
  byMethod: Partial<Record<Method, number>>
  thanked: number
}

export function eventSummary(records: LedgerRecord[]): EventSummary {
  const s: EventSummary = { count: 0, total: 0, byMethod: {}, thanked: 0 }
  for (const r of records) {
    s.count++
    s.total += r.amount
    s.byMethod[r.method] = (s.byMethod[r.method] ?? 0) + 1
    if (r.thanked) s.thanked++
  }
  return s
}

export interface ReferenceItem {
  record: LedgerRecord
  event: LedgerEvent | undefined
}

/**
 * 기록 참고 (screens.md S-07): 이 사람에게 받은 기록, 최신순.
 * 지시형 추천 문구를 만들지 않는다 — 사실만 돌려준다.
 */
export function receivedFrom(personId: string, records: LedgerRecord[], events: LedgerEvent[]): ReferenceItem[] {
  const byId = new Map(events.map((e) => [e.id, e]))
  return records
    .filter((r) => r.personId === personId && r.direction === 'received')
    .map((record) => ({ record, event: byId.get(record.eventId) }))
    .sort((a, b) => (b.event?.date ?? '').localeCompare(a.event?.date ?? '') || b.record.createdAt - a.record.createdAt)
}

/** 다가오는 상대 경조사 (오늘 포함), 가까운 순 */
export function upcomingTheirs(events: LedgerEvent[], today: string): LedgerEvent[] {
  return events
    .filter((e) => e.owner === 'theirs' && e.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
}

/**
 * 기록이 비어 있는 경조사 (screens.md S-02):
 * 행사일이 지났는데 보냄 기록이 없고, [기록 안 함]으로 빼지 않은 상대 행사. 최근 순.
 */
export function missingGiven(events: LedgerEvent[], records: LedgerRecord[], today: string): LedgerEvent[] {
  const hasGiven = new Set(records.filter((r) => r.direction === 'given').map((r) => r.eventId))
  return events
    .filter((e) => e.owner === 'theirs' && e.date < today && !e.noRecordNeeded && !hasGiven.has(e.id))
    .sort((a, b) => b.date.localeCompare(a.date))
}

export const ddays = (date: string, today: string) => daysBetween(today, date)

/** 이름으로 사람 찾기 (자동 완성). 앞부분 일치 먼저, 그다음 포함 */
export function searchPeople(people: Person[], q: string, limit = 8): Person[] {
  const s = q.trim()
  if (!s) return []
  const starts = people.filter((p) => p.name.startsWith(s))
  const contains = people.filter((p) => !p.name.startsWith(s) && (p.name.includes(s) || p.group.includes(s)))
  return [...starts, ...contains].slice(0, limit)
}

export const sameName = (people: Person[], name: string) => people.filter((p) => p.name === name.trim())

/** 사람 표시명: 동명이인이 있으면 소속을 붙인다 */
export function personLabel(p: Person): string {
  return p.group ? `${p.name} · ${p.group}` : p.name
}
