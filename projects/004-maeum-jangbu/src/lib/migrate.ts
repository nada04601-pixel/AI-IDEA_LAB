import { defaultEventTitle, type LedgerEvent } from './types'

/** 2026-10-08 이전 기본 제목 규칙: 내 행사는 "내 " + 종류 이름 */
const OLD_MINE_NAMES: Record<LedgerEvent['type'], string> = {
  wedding: '결혼식', funeral: '장례', firstBirthday: '돌잔치', birthday: '생신', opening: '개업', other: '경조사',
}

/**
 * 예전 규칙으로 자동으로 붙은 제목이면 새 기본 제목을 돌려준다. 사용자가 고친 제목이면 null.
 * 예: 내 장례 → 가족 장례, 내 돌잔치 → 아이 돌잔치, 내 칠순 → 칠순
 */
export function renameOldDefaultTitle(e: Pick<LedgerEvent, 'owner' | 'type' | 'customType' | 'title'>): string | null {
  if (e.owner !== 'mine') return null
  const custom = e.customType?.trim()
  const old = `내 ${e.type === 'other' && custom ? custom : OLD_MINE_NAMES[e.type]}`
  if (e.title !== old) return null
  const next = defaultEventTitle('mine', e.type, undefined, custom)
  return next === e.title ? null : next
}
