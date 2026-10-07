import { describe, expect, it } from 'vitest'
import { contactRows, filterRows, toPeopleInput } from '../src/lib/contactsImport'
import type { Person } from '../src/lib/types'

const existing: Person[] = [{ id: 'p1', name: '김민수', relation: 'friend', group: '', memo: '', createdAt: 1, updatedAt: 1 }]
const contacts = [
  { id: '1', name: '김민수', org: '' },
  { id: '2', name: '한지민', org: ' ○○회사 ' },
  { id: '3', name: '오정훈', org: '△△은행' },
  { id: '4', name: '오정훈', org: '△△은행' }, // 같은 연락처 중복
  { id: '5', name: '  박  지영 ', org: '' },
  { id: '6', name: '   ', org: '' },
]

describe('연락처 불러오기', () => {
  it('이름 정리, 중복 제거, 이미 있는 사람 표시, 가나다순', () => {
    const rows = contactRows(contacts, existing)
    expect(rows.map((r) => [r.contact.name, r.contact.org, r.exists])).toEqual([
      ['김민수', '', true],
      ['박 지영', '', false],
      ['오정훈', '△△은행', false],
      ['한지민', '○○회사', false],
    ])
  })

  it('이름·회사 검색', () => {
    const rows = contactRows(contacts, existing)
    expect(filterRows(rows, '은행').map((r) => r.contact.id)).toEqual(['3'])
    expect(filterRows(rows, ' ').length).toBe(4)
  })

  it('고른 사람만, 관계 일괄 지정, 회사명을 소속으로 (선택), 전화번호 없음', () => {
    const rows = contactRows(contacts, existing)
    const sel = new Set(['2', '3'])
    expect(toPeopleInput(rows, sel, 'work', true)).toEqual([
      { name: '오정훈', relation: 'work', group: '△△은행', memo: '' },
      { name: '한지민', relation: 'work', group: '○○회사', memo: '' },
    ])
    expect(toPeopleInput(rows, sel, 'friend', false).map((p) => p.group)).toEqual(['', ''])
  })
})
