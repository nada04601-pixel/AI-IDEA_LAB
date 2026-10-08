/**
 * 금액 표기 (screens.md 4-3)
 * - 목록·합계·요약: 10만, 1,845만, 3만 5천, 123,456
 * - 입력·인식 확인: 100,000원
 * - 문장 안: 10만원
 */

const comma = (n: number) => Math.round(n).toLocaleString('ko-KR')

/** 목록·합계용 줄임 표기 */
export function formatShort(amount: number): string {
  const n = Math.round(Math.abs(amount))
  const sign = amount < 0 ? '-' : ''
  if (n === 0) return '0'
  if (n % 1000 !== 0) return sign + comma(n)
  const man = Math.floor(n / 10000)
  const cheon = (n % 10000) / 1000
  if (man === 0) return `${sign}${cheon}천`
  return sign + (cheon ? `${comma(man)}만 ${cheon}천` : `${comma(man)}만`)
}

/** 입력·확인용 정확한 표기 */
export const formatFull = (amount: number) => `${comma(amount)}원`

/** 문장 안 표기: 10만원, 3만 5천원, 123,456원 */
export const formatSentence = (amount: number) => `${formatShort(amount)}원`

/**
 * 사용자가 입력한 금액 문자열을 원 단위로 바꾼다.
 * 지원: "100000", "100,000", "100,000원", "10만", "10만원", "3만5천", "3만 5천원", "1.5만"
 * unit='man' 이면 단위 없는 숫자를 만원 단위로 본다 ("15" → 150,000).
 * 읽을 수 없으면 null.
 */
export function parseAmount(input: string, unit: 'won' | 'man' = 'won'): number | null {
  const s = input.replace(/[\s,원]/g, '')
  if (!s) return null
  const m = /^(\d+(?:\.\d+)?)?(?:(만)(\d+(?:\.\d+)?)?(천)?)?$|^(\d+(?:\.\d+)?)(천)$/.exec(s)
  if (!m) return null
  let won: number
  if (m[5] !== undefined) {
    won = Number(m[5]) * 1000
  } else if (m[2]) {
    if (m[1] === undefined) return null
    won = Number(m[1]) * 10000
    if (m[3] !== undefined) won += Number(m[3]) * (m[4] ? 1000 : 1)
  } else {
    if (m[1] === undefined) return null
    won = Number(m[1]) * (unit === 'man' ? 10000 : 1)
  }
  if (!Number.isFinite(won) || won < 0) return null
  return Math.round(won)
}

/** 금액 빠른 선택 버튼 (screens.md 4-4) */
export const QUICK_AMOUNTS = [30000, 50000, 100000, 200000, 300000]
