/**
 * 연락처 여러 명 불러오기 (순수 함수, 테스트 대상)
 * 이름과 회사명만 쓴다. 전화번호는 읽지도 저장하지도 않는다 (tech-stack.md 1장).
 */
import type { Person, Relation } from './types'

export interface PhoneContact {
  id: string
  name: string
  /** 회사명 (없으면 빈 문자열) */
  org: string
}

export interface ContactRow {
  contact: PhoneContact
  /** 장부에 같은 이름이 이미 있음 */
  exists: boolean
}

/** 이름 정리 + 같은 이름·회사 중복 제거 + 이미 있는 사람 표시 (가나다순) */
export function contactRows(contacts: PhoneContact[], people: Person[]): ContactRow[] {
  const names = new Set(people.map((p) => p.name))
  const seen = new Set<string>()
  const rows: ContactRow[] = []
  for (const c of contacts) {
    const name = c.name.replace(/\s+/g, ' ').trim()
    if (!name) continue
    const key = `${name}|${c.org.trim()}`
    if (seen.has(key)) continue
    seen.add(key)
    rows.push({ contact: { ...c, name, org: c.org.trim() }, exists: names.has(name) })
  }
  return rows.sort((a, b) => a.contact.name.localeCompare(b.contact.name, 'ko'))
}

export function filterRows(rows: ContactRow[], q: string): ContactRow[] {
  const s = q.trim()
  return s ? rows.filter((r) => r.contact.name.includes(s) || r.contact.org.includes(s)) : rows
}

/** 고른 연락처 → 새로 추가할 사람 입력값 */
export function toPeopleInput(
  rows: ContactRow[],
  selected: Set<string>,
  relation: Relation,
  orgAsGroup: boolean,
): { name: string; relation: Relation; group: string; memo: string }[] {
  return rows
    .filter((r) => selected.has(r.contact.id))
    .map((r) => ({ name: r.contact.name, relation, group: orgAsGroup ? r.contact.org.slice(0, 30) : '', memo: '' }))
}
