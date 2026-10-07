import { describe, expect, it } from 'vitest'
import { parseTransferLines, readAmount, readDate, splitName, type OcrLine } from '../src/lib/ocrParse'

/**
 * 은행 앱 "거래내역조회" 화면 배치 (실제 캡처의 좌표를 본떠 만든 가짜 데이터, 이름은 모두 가명)
 * 날짜 줄 → 이름 + 같은 줄 오른쪽 금액 → 아래 줄 잔액
 */
const L = (text: string, left: number, top: number, right: number, bottom: number): OcrLine => ({ text, left, top, right, bottom })
export const BANK_SCREEN: OcrLine[] = [
  L('거래내역조회', 155, 50, 410, 100),
  L('10.06 18:26', 66, 190, 243, 222),
  L('모임회홍길동', 66, 268, 292, 315), L('100,000원', 724, 268, 922, 315), L('941,208원', 775, 345, 922, 382),
  L('10.05 14:31', 66, 492, 241, 524),
  L('김철수', 66, 570, 178, 617), L('50,000원', 749, 570, 922, 617), L('841,208원', 775, 648, 922, 685),
  L('10.04 21:38', 66, 795, 243, 827),
  L('이영희', 66, 873, 178, 920), L('100,000원', 724, 873, 922, 920), L('791,208원', 775, 950, 922, 987),
  L('10.04 12:43', 66, 1400, 243, 1432),
  L('박민준', 66, 1478, 178, 1525), L('-50,000원', 732, 1478, 922, 1525), L('591,208원', 775, 1555, 922, 1592),
  L('10.04 12:39', 66, 1703, 243, 1735),
  L('박민준', 66, 1781, 178, 1828), L('50,000원', 749, 1781, 922, 1828), L('641,208원', 775, 1858, 922, 1895),
]

describe('글자 읽기 정리', () => {
  it('금액: 쉼표·점·O 오인식, 부호로 받음/보냄', () => {
    expect(readAmount('100,000원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('-50,000원')).toEqual({ amount: 50000, direction: 'given' })
    expect(readAmount('+ 30,000원')).toEqual({ amount: 30000, direction: 'received' })
    expect(readAmount('100.000원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('1OO,OOO원')).toEqual({ amount: 100000, direction: 'received' })
    expect(readAmount('50000')).toEqual({ amount: 50000, direction: 'received' })
    expect(readAmount('홍길동')).toBeNull()
    expect(readAmount('10.06')).toBeNull()
    expect(readAmount('0원')).toBeNull()
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
    expect(rows.some((r) => [941208, 841208, 791208, 591208, 641208].includes(r.amount))).toBe(false)
    expect(unmatched).toEqual([])
  })

  it('이름과 금액이 한 줄로 읽혀도 나눈다', () => {
    const { rows } = parseTransferLines(
      [L('10.05 14:31', 66, 492, 241, 524), L('김철수 50,000원', 66, 570, 922, 617), L('841,208원', 775, 648, 922, 685)],
      '2026-10-07',
    )
    expect(rows.map((r) => [r.name, r.amount, r.date])).toEqual([['김철수', 50000, '2026-10-05']])
  })

  it('금액 짝이 없는 이름은 따로 알려 준다', () => {
    const { rows, unmatched } = parseTransferLines([L('홍길동', 66, 268, 292, 315), L('941,208원', 775, 345, 922, 382)], '2026-10-07')
    expect(rows).toEqual([])
    expect(unmatched).toEqual(['홍길동'])
  })
})
