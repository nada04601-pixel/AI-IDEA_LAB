import { describe, expect, it } from 'vitest'
import { parseTransferLines, readAmount, readDate, splitName, type OcrLine } from '../src/lib/ocrParse'
import { DEV_SAMPLE_LINES } from '../src/lib/ocrDevSample'
import { checkedSummary, draftRows } from '../src/lib/ocrImport'
import type { LedgerData } from '../src/lib/types'

/** 은행 앱 "거래내역조회" 화면 배치 (실제 캡처의 좌표를 본떠 만든 가짜 데이터, 이름은 모두 가명) */
const BANK_SCREEN = DEV_SAMPLE_LINES
const L = (text: string, left: number, top: number, right: number, bottom: number): OcrLine => ({ text, left, top, right, bottom })

describe('글자 읽기 정리', () => {
  it('금액: 쉼표·점·O 오인식, 부호로 받음/보냄', () => {
    expect(readAmount('100,000원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('-50,000원')).toEqual({ amount: 50000, direction: 'given' })
    expect(readAmount('+ 30,000원')).toEqual({ amount: 30000, direction: 'received' })
    expect(readAmount('100.000원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('1OO,OOO원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('50000원')).toEqual({ amount: 50000, direction: 'received' })
    expect(readAmount('50000')).toBeNull() // 쉼표도 원도 없는 숫자는 금액으로 보지 않는다 (전화번호 등)
    expect(readAmount('01012345678')).toBeNull()
    expect(readAmount('홍길동')).toBeNull()
    expect(readAmount('10.06')).toBeNull()
    expect(readAmount('0원')).toBeNull()
  })

  it('실제 기기에서 "원"을 잘못 읽은 경우 (2026-10-07 테스트)', () => {
    expect(readAmount('100,000A')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('591,2082l')).toEqual({ amount: 591208, direction: 'received' })
    expect(readAmount('50,000윈')).toEqual({ amount: 50000, direction: 'received' })
    expect(readAmount('-50,000 원')).toEqual({ amount: 50000, direction: 'given' })
    expect(readAmount('100,000')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('100,000원입금')).toBeNull()
    expect(readAmount('2026.10.06')).toBeNull()
  })

  it('날짜: 연도가 없으면 오늘 이전의 가장 가까운 날', () => {
    expect(readDate('10.06 18:26', '2026-10-07')).toBe('2026-10-06')
    expect(readDate('12.30 09:00', '2026-01-05')).toBe('2025-12-30')
    expect(readDate('2024.05.18', '2026-10-07')).toBe('2024-05-18')
    expect(readDate('10월 4일 (토)', '2026-10-07')).toBe('2026-10-04')
    expect(readDate('13.40', '2026-10-07')).toBeNull()
  })

  it('이름: 모임명+이름이면 나눠서 제안', () => {
    expect(splitName('홍길동')).toEqual({ name: '홍길동', group: '', flags: [] })
    expect(splitName('모임회홍길동')).toEqual({ name: '홍길동', group: '모임회', flags: ['name-split'] })
    expect(splitName('ABC 홍길동')).toMatchObject({ name: 'ABC 홍길동', flags: ['name-check'] })
  })
})

describe('이체 내역 화면', () => {
  it('같은 줄 금액만 거래로, 아래 줄 잔액은 무시', () => {
    const { rows, unmatched } = parseTransferLines(BANK_SCREEN, '2026-10-07')
    expect(rows.map((r) => [r.name, r.group, r.amount, r.direction, r.date])).toEqual([
      ['홍길동', '모임회', 100000, 'received', '2026-10-06'],
      ['김철수', '', 50000, 'received', '2026-10-05'],
      ['이영희', '', 100000, 'received', '2026-10-04'],
      ['박민준', '', 50000, 'given', '2026-10-04'],
      ['박민준', '', 50000, 'received', '2026-10-04'],
    ])
    expect(rows[0].flags).toEqual(['name-split'])
    expect(rows.some((r) => [312500, 212500, 162500, 62500, 112500].includes(r.amount))).toBe(false)
    expect(unmatched).toEqual([])
  })

  it('실제 기기처럼 "원"이 잘못 읽혀도 같은 줄 금액과 짝짓는다', () => {
    const misread = DEV_SAMPLE_LINES.map((l) =>
      l.text === '100,000원' ? { ...l, text: '100,000A' } : l.text === '62,500원' ? { ...l, text: '62,5002l' } : l,
    )
    const { rows, unmatched } = parseTransferLines(misread, '2026-10-07')
    expect(rows.map((r) => [r.name, r.amount])).toEqual([
      ['홍길동', 100000], ['김철수', 50000], ['이영희', 100000], ['박민준', 50000], ['박민준', 50000],
    ])
    expect(unmatched).toEqual([])
  })

  it('이름과 금액이 한 줄로 읽혀도 나눈다', () => {
    const { rows } = parseTransferLines(
      [L('10.05 14:31', 66, 492, 241, 524), L('김철수 50,000원', 66, 570, 922, 617), L('212,500원', 775, 648, 922, 685)],
      '2026-10-07',
    )
    expect(rows.map((r) => [r.name, r.amount, r.date])).toEqual([['김철수', 50000, '2026-10-05']])
  })

  it('금액 짝이 없는 이름은 따로 알려 준다', () => {
    const { rows, unmatched } = parseTransferLines([L('홍길동', 66, 268, 292, 315), L('312,500원', 775, 345, 922, 382)], '2026-10-07')
    expect(rows).toEqual([])
    expect(unmatched).toEqual(['홍길동'])
  })
})

describe('확인 화면 줄 (S-10)', () => {
  const parsed = parseTransferLines(BANK_SCREEN, '2026-10-07').rows.map((r) => ({ ...r, image: 0 }))
  const data: LedgerData = {
    people: [
      { id: 'p1', name: '김철수', relation: 'friend', group: '', memo: '', createdAt: 1, updatedAt: 1 },
      { id: 'p2', name: '이영희', relation: 'work', group: 'A사', memo: '', createdAt: 1, updatedAt: 1 },
      { id: 'p3', name: '이영희', relation: 'work', group: 'B사', memo: '', createdAt: 1, updatedAt: 1 },
    ],
    events: [{ id: 'e1', owner: 'mine', personId: null, type: 'wedding', title: '내 결혼식', date: '2026-10-10', place: '', remind: false, noRecordNeeded: false, createdAt: 1, updatedAt: 1 }],
    records: [{ id: 'r1', eventId: 'e1', personId: 'p1', direction: 'received', amount: 50000, method: 'transfer', attended: null, thanked: false, memo: '', source: 'manual', createdAt: 1, updatedAt: 1 }],
  }

  it('받음을 고르면: 출금 줄·이미 있는 기록은 빼고, 동명이인은 확인 요청', () => {
    const rows = draftRows(parsed, data, { direction: 'received', eventId: 'e1' })
    expect(rows.map((r) => [r.name, r.checked, r.personId, r.note])).toEqual([
      ['홍길동', true, null, null],
      ['김철수', false, 'p1', '이미 있는 기록이에요'],
      ['이영희', true, null, '이름이 같은 사람이 있어요. 같은 사람이면 골라 주세요'],
      ['박민준', false, null, '출금(보낸 돈)이라 뺐어요'],
      ['박민준', true, null, null],
    ])
    expect(checkedSummary(rows)).toEqual({ count: 3, total: 250000 })
  })

  it('보냄을 고르면 입금 줄을 뺀다', () => {
    const rows = draftRows(parsed, data, { direction: 'given' })
    expect(rows.filter((r) => r.checked).map((r) => [r.name, r.amount])).toEqual([['박민준', 50000]])
  })

  it('겹쳐 찍은 사진에서 같은 내역이 두 번 나오면 하나만', () => {
    const twice = [...parsed.slice(0, 2), ...parsed.slice(0, 2).map((r) => ({ ...r, image: 1 }))]
    const rows = draftRows(twice, { people: [], events: [], records: [] }, { direction: 'received' })
    expect(rows.map((r) => r.checked)).toEqual([true, true, false, false])
    expect(rows[2].note).toBe('같은 내역을 두 번 읽었어요')
  })
})
