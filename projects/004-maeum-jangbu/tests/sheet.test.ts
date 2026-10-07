import { describe, expect, it } from 'vitest'
import { RECORD_COLUMNS, parseCsv, personRows, recordRows, rosters, scopeData, sheetName, toCsv } from '../src/lib/sheet'
import { mapHeader, tableToData, toDateKey } from '../src/lib/importData'
import { buildWorkbook, readWorkbook } from '../src/lib/excel'
import { matchPeople, mergeData } from '../src/lib/backup'
import type { LedgerData, LedgerEvent, LedgerRecord, Person } from '../src/lib/types'

const person = (id: string, name: string, group = '', relation: Person['relation'] = 'friend'): Person => ({
  id, name, relation, group, memo: '', createdAt: 1, updatedAt: 1,
})
const event = (id: string, owner: 'mine' | 'theirs', date: string, title: string, personId: string | null = null): LedgerEvent => ({
  id, owner, personId, type: 'wedding', title, date, place: '', remind: false, noRecordNeeded: false, createdAt: 1, updatedAt: 1,
})
const record = (id: string, eventId: string, personId: string, direction: 'received' | 'given', amount: number, extra: Partial<LedgerRecord> = {}): LedgerRecord => ({
  id, eventId, personId, direction, amount, method: 'cash', attended: null, thanked: false, memo: '', source: 'manual',
  createdAt: Number(id.replace(/\D/g, '')) || 1, updatedAt: 1, ...extra,
})

const data: LedgerData = {
  people: [person('p1', '김민수', '대학 동기'), person('p2', '박지영', '○○회사', 'work'), person('p3', '이현우', '', 'relative')],
  events: [
    event('e1', 'mine', '2024-05-18', '내 결혼식'),
    event('t1', 'theirs', '2026-10-10', '김민수 결혼식', 'p1'),
  ],
  records: [
    record('r1', 'e1', 'p1', 'received', 100000, { thanked: true, attended: true }),
    record('r2', 'e1', 'p2', 'received', 50000, { method: 'transfer', memo: '쉼표, "따옴표"' }),
    record('r3', 'e1', 'p3', 'received', 0, { method: 'flower' }),
    record('r4', 't1', 'p1', 'given', 100000, { method: 'transfer', attended: true }),
  ],
}

describe('내보내기 표', () => {
  it('전체 내역 = 가져오기 양식 열 순서', () => {
    const rows = recordRows(data)
    expect(rows[0]).toEqual(['2024-05-18', '내 결혼식', '결혼', '김민수', '친구', '대학 동기', '받음', 100000, '현금', '참석', '완료', ''])
    expect(rows.at(-1)).toEqual(['2026-10-10', '김민수 결혼식', '결혼', '김민수', '친구', '대학 동기', '보냄', 100000, '계좌이체', '참석', '', ''])
    expect(rows[0]).toHaveLength(RECORD_COLUMNS.length)
  })

  it('사람별 장부: 받은·보낸 총액과 차이', () => {
    expect(personRows(data)).toEqual([
      ['김민수', '친구', '대학 동기', 100000, 100000, 0, '2026-10-10'],
      ['박지영', '직장', '○○회사', 50000, 0, 50000, '2024-05-18'],
      ['이현우', '친척', '', 0, 0, 0, '2024-05-18'],
    ])
  })

  it('행사별 명단: 내 행사만, 이름순, 합계', () => {
    const r = rosters(data)
    expect(r).toHaveLength(1)
    expect(r[0].total).toBe(150000)
    expect(r[0].rows.map((x) => x[1])).toEqual(['김민수', '박지영', '이현우'])
  })

  it('범위: 행사 / 사람 / 기간', () => {
    expect(scopeData(data, { kind: 'event', eventId: 'e1' }).records).toHaveLength(3)
    expect(scopeData(data, { kind: 'person', personId: 'p1' }).records.map((r) => r.id)).toEqual(['r1', 'r4'])
    expect(scopeData(data, { kind: 'period', from: '2026-01-01', to: '2026-12-31' }).records.map((r) => r.id)).toEqual(['r4'])
  })

  it('시트 이름: 금지 문자 제거, 31자 이하, 중복 번호', () => {
    const used = new Set<string>()
    expect(sheetName('내 결혼식 [1/2]', used)).toBe('내 결혼식  1 2')
    expect(sheetName('내 결혼식  1 2', used)).toBe('내 결혼식  1 2 2')
    expect(sheetName('가'.repeat(40), used).length).toBeLessThanOrEqual(31)
  })

  it('CSV: BOM, 쉼표·따옴표 처리, 다시 읽으면 같은 값', () => {
    const csv = toCsv(RECORD_COLUMNS, recordRows(data))
    expect(csv.startsWith('﻿날짜,')).toBe(true)
    expect(csv).toContain('"쉼표, ""따옴표"""')
    const back = parseCsv(csv)
    expect(back[0]).toEqual([...RECORD_COLUMNS])
    expect(back.find((r) => r[3] === '박지영')?.[11]).toBe('쉼표, "따옴표"')
  })
})

describe('가져오기', () => {
  it('날짜 형식', () => {
    expect(toDateKey('2024.5.18')).toBe('2024-05-18')
    expect(toDateKey('2024/05/18')).toBe('2024-05-18')
    expect(toDateKey('2024년 5월 18일')).toBe('2024-05-18')
    expect(toDateKey(new Date(Date.UTC(2024, 4, 18)))).toBe('2024-05-18')
    expect(toDateKey(45430)).toBe('2024-05-18') // 엑셀 일련번호
    expect(toDateKey('5월 18일')).toBeNull()
    expect(toDateKey('2024-13-01')).toBeNull()
  })

  it('흔한 열 이름도 알아본다', () => {
    const { fields, unknown } = mapHeader(['성명', '축의금', '일자', '비고', '테이블'])
    expect(fields).toEqual(['name', 'amount', 'date', 'memo', null])
    expect(unknown).toEqual(['테이블'])
  })

  it('직접 만든 축의금 표: 금액 표기 여러 가지, 잘못된 줄은 이유와 함께 제외', () => {
    const table = [
      ['일자', '행사', '성명', '관계', '축의금', '방법'],
      ['2024.05.18', '우리 결혼식', '김민수', '친구', '10만원', '현금'],
      ['2024.05.18', '우리 결혼식', '박지영', '직장', '50,000', '계좌'],
      ['2024.05.18', '우리 결혼식', '이현우', '친척', '', '화환'],
      ['2024.05.18', '우리 결혼식', '', '', '30000', ''],
      ['날짜없음', '우리 결혼식', '최서연', '', '30000', ''],
      ['2024.05.18', '우리 결혼식', '정우진', '', '많이', ''],
    ]
    const { data: d, issues } = tableToData(table, 1000)
    expect(d.people.map((p) => p.name)).toEqual(['김민수', '박지영', '이현우'])
    expect(d.events).toHaveLength(1)
    expect(d.events[0]).toMatchObject({ owner: 'mine', title: '우리 결혼식', type: 'wedding', date: '2024-05-18' })
    expect(d.records.map((r) => [r.amount, r.method, r.direction, r.source])).toEqual([
      [100000, 'cash', 'received', 'import'], [50000, 'transfer', 'received', 'import'], [0, 'flower', 'received', 'import'],
    ])
    expect(d.people[1].relation).toBe('work')
    expect(issues.map((x) => x.line)).toEqual([5, 6, 7])
    expect(issues[1].reason).toContain('날짜')
  })

  it('보냄 줄은 그 사람의 상대 행사로, 부친상은 장례로', () => {
    const { data: d } = tableToData([
      ['날짜', '행사', '이름', '받음/보냄', '금액'],
      ['2026-09-14', '박지영 부친상', '박지영', '보냄', '5만'],
    ])
    expect(d.events[0]).toMatchObject({ owner: 'theirs', type: 'funeral', personId: d.people[0].id })
    expect(d.records[0]).toMatchObject({ direction: 'given', amount: 50000 })
  })

  it('행사 열이 없는 명단은 같은 날 내 행사와 합쳐진다', () => {
    const { data: d } = tableToData([
      ['일자', '성명', '축의금'],
      ['2024.05.18', '김민수', '10만'],
      ['2024.05.18', '한지민', '5만'],
    ])
    expect(d.events[0]).toMatchObject({ owner: 'mine', type: 'other' })
    // 김민수는 소속이 달라(엑셀엔 없음) 묻는 대상 → "같은 사람"으로 답했다고 가정
    const { sameAs, conflicts } = matchPeople(data, d)
    expect(conflicts.map((c) => c.incoming.name)).toEqual(['김민수'])
    const merged = mergeData(data, d, { ...sameAs, [conflicts[0].incoming.id]: conflicts[0].existing.id })
    expect(merged.added).toEqual({ people: 1, events: 0, records: 1 }) // 김민수 10만은 중복
    expect(merged.result.records.find((r) => r.amount === 50000)?.eventId).toBe('e1')
  })

  it('필수 열이 없으면 알려 준다', () => {
    expect(() => tableToData([['이름', '금액']])).toThrow('"날짜" 열')
  })
})

describe('엑셀 왕복', () => {
  it('내보낸 엑셀을 다시 가져오면 같은 내용, 기존 장부와 합치면 모두 중복', async () => {
    const buf = await buildWorkbook(data, '마음장부')
    const table = await readWorkbook(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
    expect(table[0]).toEqual([...RECORD_COLUMNS])
    const { data: back, issues } = tableToData(table)
    expect(issues).toEqual([])
    expect(back.records.map((r) => [r.direction, r.amount, r.method, r.thanked]).sort()).toEqual(
      data.records.map((r) => [r.direction, r.amount, r.method, r.thanked]).sort(),
    )
    expect(back.people.map((p) => `${p.name}|${p.group}|${p.relation}`).sort()).toEqual(
      data.people.map((p) => `${p.name}|${p.group}|${p.relation}`).sort(),
    )
    // 이름·소속이 같아 묻지 않고 같은 사람으로 연결 → 내용이 같은 기록은 전부 중복으로 건너뛴다
    const { sameAs, conflicts } = matchPeople(data, back)
    expect(conflicts).toEqual([])
    const merged = mergeData(data, back, sameAs)
    expect(merged.added).toEqual({ people: 0, events: 0, records: 0 })
  })
})
