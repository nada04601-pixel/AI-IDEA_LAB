/**
 * 내보내기용 표 데이터 (순수 함수, 테스트 대상) — tech-stack.md 5-3
 * 엑셀과 CSV가 같은 행을 쓴다. "전체 내역" 열 구성 = 가져오기 양식 (왕복 편집).
 */
import { totalsByPerson } from './ledger'
import {
  directionLabel, eventKindLabel, methodLabel, relationLabel,
  type LedgerData, type LedgerEvent, type LedgerRecord, type Person,
} from './types'

export type Scope =
  | { kind: 'all' }
  | { kind: 'event'; eventId: string }
  | { kind: 'period'; from: string; to: string }
  | { kind: 'person'; personId: string }

/** 범위에 맞는 내역만 남긴 데이터 */
export function scopeData(data: LedgerData, scope: Scope): LedgerData {
  if (scope.kind === 'all') return data
  const eventsById = new Map(data.events.map((e) => [e.id, e]))
  const keep = (r: LedgerRecord) => {
    const e = eventsById.get(r.eventId)
    if (scope.kind === 'event') return r.eventId === scope.eventId
    if (scope.kind === 'person') return r.personId === scope.personId
    return !!e && e.date >= scope.from && e.date <= scope.to
  }
  const records = data.records.filter(keep)
  const eventIds = new Set(records.map((r) => r.eventId))
  if (scope.kind === 'event') eventIds.add(scope.eventId)
  const personIds = new Set(records.map((r) => r.personId))
  if (scope.kind === 'person') personIds.add(scope.personId)
  return {
    people: data.people.filter((p) => personIds.has(p.id)),
    events: data.events.filter((e) => eventIds.has(e.id)),
    records,
  }
}

/** 가져오기 양식과 같은 열 (순서 고정) */
export const RECORD_COLUMNS = [
  '날짜', '행사', '행사 종류', '이름', '관계', '소속', '받음/보냄', '금액', '방식', '참석', '감사 인사', '메모',
] as const

export type Cell = string | number
export type Row = Cell[]

const attendedText = (v: boolean | null) => (v === null ? '' : v ? '참석' : '불참')

function joined(data: LedgerData) {
  const people = new Map(data.people.map((p) => [p.id, p]))
  const events = new Map(data.events.map((e) => [e.id, e]))
  return data.records
    .map((r) => ({ r, p: people.get(r.personId), e: events.get(r.eventId) }))
    .filter((x): x is { r: LedgerRecord; p: Person; e: LedgerEvent } => !!x.p && !!x.e)
}

/** 전체 내역: 날짜순(오래된 것부터), 같은 행사 안에서는 입력순 */
export function recordRows(data: LedgerData): Row[] {
  return joined(data)
    .sort((a, b) => a.e.date.localeCompare(b.e.date) || a.e.title.localeCompare(b.e.title) || a.r.createdAt - b.r.createdAt)
    .map(({ r, p, e }) => [
      e.date, e.title, eventKindLabel(e), p.name, relationLabel(p.relation), p.group,
      directionLabel(r.direction), r.amount, methodLabel(r.method), attendedText(r.attended),
      r.direction === 'received' && r.thanked ? '완료' : '', r.memo,
    ])
}

export const PERSON_COLUMNS = ['이름', '관계', '소속', '받은 총액', '보낸 총액', '차이 (받음-보냄)', '마지막 기록일'] as const

export function personRows(data: LedgerData): Row[] {
  const totals = totalsByPerson(data.records)
  const lastDate = new Map<string, string>()
  for (const { r, e } of joined(data)) if ((lastDate.get(r.personId) ?? '') < e.date) lastDate.set(r.personId, e.date)
  return data.people
    .filter((p) => totals.has(p.id))
    .sort((a, b) => a.name.localeCompare(b.name, 'ko'))
    .map((p) => {
      const t = totals.get(p.id)!
      return [p.name, relationLabel(p.relation), p.group, t.received, t.given, t.received - t.given, lastDate.get(p.id) ?? '']
    })
}

export const ROSTER_COLUMNS = ['번호', '이름', '관계', '소속', '금액', '방식', '참석', '감사 인사'] as const

export interface Roster {
  event: LedgerEvent
  rows: Row[]
  total: number
}

/** 행사별 명단: 내 행사마다 받은 내역 (이름순) */
export function rosters(data: LedgerData): Roster[] {
  const all = joined(data)
  return data.events
    .filter((e) => e.owner === 'mine')
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((event) => {
      const list = all
        .filter((x) => x.e.id === event.id && x.r.direction === 'received')
        .sort((a, b) => a.p.name.localeCompare(b.p.name, 'ko'))
      return {
        event,
        total: list.reduce((s, x) => s + x.r.amount, 0),
        rows: list.map(({ r, p }, i) => [
          i + 1, p.name, relationLabel(p.relation), p.group, r.amount, methodLabel(r.method), attendedText(r.attended), r.thanked ? '완료' : '',
        ]),
      }
    })
    .filter((x) => x.rows.length > 0)
}

/** 엑셀 시트 이름: 31자 이하, 금지 문자 제거, 중복이면 번호 */
export function sheetName(base: string, used: Set<string>): string {
  const clean = base.replace(/[\\/?*[\]:]/g, ' ').trim().slice(0, 28) || '시트'
  let name = clean
  for (let i = 2; used.has(name); i++) name = `${clean.slice(0, 26)} ${i}`
  used.add(name)
  return name
}

/** CSV (엑셀에서 한글이 깨지지 않게 UTF-8 BOM, 줄바꿈 CRLF) */
export function toCsv(header: readonly string[], rows: Row[]): string {
  const esc = (v: Cell) => {
    const s = String(v)
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return '﻿' + [header, ...rows].map((r) => r.map(esc).join(',')).join('\r\n') + '\r\n'
}

/** CSV 읽기 (따옴표·줄바꿈 포함 칸 지원) */
export function parseCsv(text: string): string[][] {
  const s = text.replace(/^﻿/, '')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (quoted) {
      if (c === '"' && s[i + 1] === '"') { cell += '"'; i++ }
      else if (c === '"') quoted = false
      else cell += c
    } else if (c === '"') quoted = true
    else if (c === ',') { row.push(cell); cell = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++
      row.push(cell); rows.push(row); row = []; cell = ''
    } else cell += c
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row) }
  return rows.filter((r) => r.some((v) => v.trim() !== ''))
}

/** 일괄 등록용 빈 CSV 양식 (머리글만). 작성 방법은 앱 화면에서 안내한다 */
export const templateCsv = () => toCsv(RECORD_COLUMNS, [])
