/**
 * 인식 결과 → 확인 화면의 줄 (순수 함수, 테스트 대상) — screens.md S-10
 * - 기존 사람과 이름(·소속)이 같으면 연결
 * - 고른 방향(받음/보냄)과 다른 줄, 이미 있는 기록, 같은 사진을 두 번 읽은 줄은 기본으로 체크 해제 + 이유
 */
import type { Direction, LedgerData } from './types'
import type { OcrRow } from './ocrParse'

export interface DraftRow extends OcrRow {
  /** 몇 번째 사진 */
  image: number
  checked: boolean
  /** 연결할 기존 사람 (없으면 새 사람) */
  personId: string | null
  /** 체크 해제·확인 이유 */
  note: string | null
}

export interface DraftOptions {
  direction: Direction
  /** 받음일 때 넣을 내 행사 (새 행사면 undefined) */
  eventId?: string
}

export function matchPerson(data: LedgerData, name: string, group: string): { personId: string | null; note: string | null } {
  const same = data.people.filter((p) => p.name === name)
  if (!same.length) return { personId: null, note: null }
  const exact = same.filter((p) => p.group === group)
  if (exact.length === 1) return { personId: exact[0].id, note: null }
  if (same.length === 1 && !group) return { personId: same[0].id, note: null }
  return { personId: null, note: `이름이 같은 사람이 있어요. 같은 사람이면 골라 주세요` }
}

export function draftRows(rows: (OcrRow & { image: number })[], data: LedgerData, opts: DraftOptions): DraftRow[] {
  const eventsById = new Map(data.events.map((e) => [e.id, e]))
  const seen = new Set<string>()
  return rows.map((r) => {
    const { personId, note: personNote } = matchPerson(data, r.name, r.group)
    let note: string | null = null
    if (r.direction !== opts.direction) {
      note = r.direction === 'given' ? '출금(보낸 돈)이라 뺐어요' : '입금(받은 돈)이라 뺐어요'
    } else {
      const sameKey = `${r.name}|${r.amount}|${r.date}|${r.direction}`
      if (seen.has(sameKey)) note = '같은 내역을 두 번 읽었어요'
      seen.add(sameKey)
      if (!note && personId) {
        const dup = data.records.some((x) => {
          if (x.personId !== personId || x.amount !== r.amount || x.direction !== r.direction) return false
          if (opts.direction === 'received') return !!opts.eventId && x.eventId === opts.eventId
          return eventsById.get(x.eventId)?.date === r.date
        })
        if (dup) note = '이미 있는 기록이에요'
      }
    }
    return { ...r, checked: note === null, personId, note: note ?? personNote }
  })
}

export function checkedSummary(rows: DraftRow[]): { count: number; total: number } {
  const on = rows.filter((r) => r.checked)
  return { count: on.length, total: on.reduce((s, r) => s + r.amount, 0) }
}
