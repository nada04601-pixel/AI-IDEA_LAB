/**
 * 엑셀·CSV 가져오기 (순수 함수, 테스트 대상) — idea.md 3-3 "엑셀 왕복 편집"
 * 내보낸 "전체 내역" 열 구성을 그대로 읽는다. 열 이름이 조금 달라도 흔한 이름은 알아본다.
 * 결과는 백업 복원과 같은 합치기 흐름(mergeData)으로 들어간다.
 */
import { parseAmount } from './money'
import { isDateKey } from './date'
import {
  EVENT_TYPES, METHODS, RELATIONS, defaultEventTitle, uuid,
  type Direction, type EventType, type LedgerData, type LedgerEvent, type Method, type Person, type Relation,
} from './types'

type Field = 'date' | 'event' | 'type' | 'name' | 'relation' | 'group' | 'direction' | 'amount' | 'method' | 'attended' | 'thanked' | 'memo'

/** 열 이름 → 필드 (공백 무시) */
const ALIASES: Record<Field, string[]> = {
  date: ['날짜', '일자', '행사일', '날자', '일시'],
  event: ['행사', '행사명', '경조사', '제목'],
  type: ['행사종류', '종류', '구분'],
  name: ['이름', '성명', '성함', '보낸사람', '받은사람', '하객', '이름(성명)'],
  relation: ['관계'],
  group: ['소속', '설명', '비고(소속)', '회사', '소속·설명'],
  direction: ['받음/보냄', '받음/줌', '받음보냄', '주고받음', '방향'],
  amount: ['금액', '축의금', '부의금', '조의금', '금액(원)', '액수'],
  method: ['방식', '전달방식', '방법'],
  attended: ['참석', '참석여부'],
  thanked: ['감사인사', '감사', '답례'],
  memo: ['메모', '비고'],
}

const norm = (s: unknown) => String(s ?? '').replace(/\s/g, '')

export interface ImportIssue {
  /** 원본 파일의 줄 번호 (머리글 = 1) */
  line: number
  reason: string
}

export interface ImportResult {
  data: LedgerData
  issues: ImportIssue[]
  /** 알아보지 못한 열 이름 */
  unknownColumns: string[]
}

export function mapHeader(header: unknown[]): { fields: (Field | null)[]; unknown: string[] } {
  const used = new Set<Field>()
  const unknown: string[] = []
  const fields = header.map((h) => {
    const n = norm(h)
    const f = (Object.keys(ALIASES) as Field[]).find((k) => !used.has(k) && ALIASES[k].includes(n)) ?? null
    if (f) used.add(f)
    else if (n) unknown.push(String(h))
    return f
  })
  return { fields, unknown }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** 엑셀 날짜(Date 또는 일련번호)·"2024.05.18"·"2024/5/18"·"2024-05-18" → YYYY-MM-DD */
export function toDateKey(v: unknown): string | null {
  if (v instanceof Date && !Number.isNaN(v.getTime())) {
    // 엑셀 날짜는 UTC 자정으로 읽힌다
    return `${v.getUTCFullYear()}-${pad(v.getUTCMonth() + 1)}-${pad(v.getUTCDate())}`
  }
  if (typeof v === 'number' && v > 20000 && v < 80000) {
    const d = new Date(Date.UTC(1899, 11, 30) + v * 86400000)
    return toDateKey(d)
  }
  const m = /^(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})\s*일?$/.exec(String(v ?? '').trim())
  if (!m) return null
  const key = `${m[1]}-${pad(Number(m[2]))}-${pad(Number(m[3]))}`
  return isDateKey(key) && Number(m[2]) <= 12 && Number(m[3]) <= 31 ? key : null
}

function toAmount(v: unknown): number | null {
  if (typeof v === 'number') return Number.isFinite(v) && v >= 0 ? Math.round(v) : null
  const s = String(v ?? '').trim()
  return s === '' ? 0 : parseAmount(s)
}

const pickLabel = <T extends string>(v: unknown, list: { value: T; label: string }[], fallback: T): T => {
  const n = norm(v)
  if (!n) return fallback
  return list.find((x) => x.label === n || norm(x.label) === n || x.value === n)?.value ?? fallback
}

function toDirection(v: unknown): Direction | null {
  const n = norm(v)
  if (!n) return 'received'
  if (/^(받음|받은|받|수입|received)/.test(n)) return 'received'
  if (/^(보냄|보낸|줌|준|냄|지출|given)/.test(n)) return 'given'
  return null
}

function toType(v: unknown, title: string): EventType {
  const n = norm(v) || title
  if (/결혼|웨딩|혼례/.test(n)) return 'wedding'
  if (/장례|부고|별세|조의|부의|상$/.test(n)) return 'funeral'
  if (/돌/.test(n)) return 'firstBirthday'
  if (/생신|생일|칠순|팔순|환갑|회갑/.test(n)) return 'birthday'
  if (/개업|개원|창업/.test(n)) return 'opening'
  return pickLabel(v, EVENT_TYPES, 'other')
}

function toMethod(v: unknown): Method {
  const n = norm(v)
  if (/계좌|이체|송금/.test(n)) return 'transfer'
  if (/화환|꽃/.test(n)) return 'flower'
  if (/선물/.test(n)) return 'gift'
  if (!n || /현금/.test(n)) return 'cash'
  return pickLabel(v, METHODS, 'other')
}

function toAttended(v: unknown): boolean | null {
  const n = norm(v)
  if (/^(참석|예|o|y|yes|✓|○)$/i.test(n)) return true
  if (/^(불참|아니오|x|n|no)$/i.test(n)) return false
  return null
}

const toThanked = (v: unknown) => /^(완료|o|y|yes|예|✓|○|v|true|1)$/i.test(norm(v))

/**
 * 표(첫 줄 = 머리글)를 장부 데이터로 바꾼다.
 * - 사람: 이름 + 소속이 같으면 같은 사람
 * - 행사: 받음이면 내 행사, 보냄이면 그 사람의 상대 행사. 날짜 + 행사명(+ 사람)이 같으면 같은 행사
 * - 날짜·이름·금액을 읽을 수 없는 줄은 issues로 돌려주고 제외
 */
export function tableToData(table: unknown[][], now = Date.now()): ImportResult {
  if (!table.length) throw new Error('파일에 내용이 없어요.')
  const { fields, unknown } = mapHeader(table[0])
  const col = (f: Field) => fields.indexOf(f)
  for (const need of ['date', 'name', 'amount'] as Field[]) {
    if (col(need) < 0) {
      const label = { date: '날짜', name: '이름', amount: '금액' }[need as 'date']
      throw new Error(`"${label}" 열을 찾지 못했어요. 첫 줄에 열 이름(날짜, 이름, 금액 등)이 있는지 확인해 주세요.`)
    }
  }
  const get = (row: unknown[], f: Field) => (col(f) >= 0 ? row[col(f)] : undefined)
  const str = (v: unknown) => (v === undefined || v === null ? '' : String(v).trim())

  const people = new Map<string, Person>()
  const events = new Map<string, LedgerEvent>()
  const data: LedgerData = { people: [], events: [], records: [] }
  const issues: ImportIssue[] = []

  table.slice(1).forEach((row, i) => {
    const line = i + 2
    if (row.every((v) => str(v) === '')) return
    const name = str(get(row, 'name'))
    const date = toDateKey(get(row, 'date'))
    const amount = toAmount(get(row, 'amount'))
    const direction = toDirection(get(row, 'direction'))
    if (!name) return issues.push({ line, reason: '이름이 비어 있어요' })
    if (!date) return issues.push({ line, reason: `날짜를 읽을 수 없어요 (${str(get(row, 'date')) || '빈 칸'})` })
    if (amount === null) return issues.push({ line, reason: `금액을 읽을 수 없어요 (${str(get(row, 'amount'))})` })
    if (!direction) return issues.push({ line, reason: `받음/보냄을 알 수 없어요 (${str(get(row, 'direction'))})` })

    const group = str(get(row, 'group'))
    const relation: Relation = pickLabel(get(row, 'relation'), RELATIONS, 'other')
    const pKey = `${name}|${group}`
    let person = people.get(pKey)
    if (!person) {
      person = { id: uuid(), name, relation, group, memo: '', createdAt: now, updatedAt: now }
      people.set(pKey, person)
      data.people.push(person)
    }

    const title0 = str(get(row, 'event'))
    const type = toType(get(row, 'type'), title0)
    const owner = direction === 'received' ? 'mine' : 'theirs'
    const title = title0 || defaultEventTitle(owner, type, name)
    const eKey = owner === 'mine' ? `mine|${date}|${title}` : `theirs|${date}|${title}|${person.id}`
    let event = events.get(eKey)
    if (!event) {
      event = {
        id: uuid(), owner, personId: owner === 'theirs' ? person.id : null, type, title, date, place: '',
        remind: false, noRecordNeeded: false, createdAt: now, updatedAt: now,
      }
      events.set(eKey, event)
      data.events.push(event)
    }

    data.records.push({
      id: uuid(), eventId: event.id, personId: person.id, direction, amount,
      method: toMethod(get(row, 'method')), attended: toAttended(get(row, 'attended')),
      thanked: direction === 'received' && toThanked(get(row, 'thanked')), memo: str(get(row, 'memo')),
      source: 'import', createdAt: now + i, updatedAt: now + i,
    })
  })
  return { data, issues, unknownColumns: unknown }
}
