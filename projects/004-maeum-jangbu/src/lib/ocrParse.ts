/**
 * 사진에서 읽은 글자(줄 + 위치) → 이름·금액·받음/보냄 (순수 함수, 테스트 대상) — idea.md 3-2, tech-stack.md 3장
 *
 * 은행 앱 이체 내역 화면 기준:
 *   10.06 18:26                 ← 날짜·시각
 *   사모회홍길동      100,000원   ← 이름(메모)과 같은 줄의 금액 = 거래 금액
 *                    941,208원   ← 아래 줄 금액 = 잔액 (무시)
 * - 금액 앞에 "-"가 있으면 보냄(출금), 없거나 "+"면 받음(입금)
 * - 이름 칸에 "모임명+이름"이 붙어 있으면(5~8글자 한글) 뒤 3글자를 이름, 앞을 소속으로 제안하고 확인 표시
 * 계산(합계)은 여기서 하지 않는다. 결과는 사용자가 확인한 뒤에만 저장한다.
 */
import type { Direction } from './types'

export interface OcrLine {
  text: string
  left: number
  top: number
  right: number
  bottom: number
}

export type OcrFlag = 'name-split' | 'name-check' | 'amount-check'

export interface OcrRow {
  /** 화면에서 줄을 구분하는 값 */
  key: string
  name: string
  group: string
  amount: number
  direction: Direction
  /** YYYY-MM-DD (날짜 줄이 없으면 null) */
  date: string | null
  /** 원래 읽은 글자 (이름 줄 + 금액 줄) */
  raw: string
  /** 사진에서 이 내역이 있는 영역 (이름 줄 ~ 금액 줄) */
  box: { left: number; top: number; right: number; bottom: number }
  flags: OcrFlag[]
}

const AMOUNT = /^([+\-−])?\s*₩?\s*(\d{1,3}(?:[,.]\d{3})+|\d{4,})\s*원?$/
const TRAILING_AMOUNT = /^(.*?\S)\s+([+\-−]?\s*₩?\s*(?:\d{1,3}(?:[,.]\d{3})+|\d{4,})\s*원)$/
const DATE = /^(?:(\d{4})\s*[.\-/년]\s*)?(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?(?:\s*\(?[월화수목금토일]\)?)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?$/
/** 이름이 아닌 화면 글자 */
const UI_WORDS = /^(거래내역(조회)?|입출금내역|이체내역|입금|출금|전체|잔액|조회|검색|필터|오늘|최근|\d+개월|더보기|정렬|최신순|과거순|입금내역|출금내역|내역|통장|계좌)$/
const HANGUL_ONLY = /^[가-힣]+$/

const center = (l: OcrLine) => (l.top + l.bottom) / 2
const height = (l: OcrLine) => Math.max(1, l.bottom - l.top)

/** OCR이 자주 헷갈리는 글자 정리: 숫자처럼 생긴 덩어리 안의 O → 0, 공백 정리 */
export function cleanText(s: string): string {
  return s
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[+\-−]?[\dOo][\dOo,.]*원?/g, (tok) => (/\d/.test(tok) ? tok.replace(/[Oo]/g, '0') : tok))
}

export function readAmount(text: string): { amount: number; direction: Direction } | null {
  const m = AMOUNT.exec(cleanText(text))
  if (!m) return null
  const amount = Number(m[2].replace(/[,.]/g, ''))
  if (!Number.isFinite(amount) || amount <= 0) return null
  return { amount, direction: m[1] === '-' || m[1] === '−' ? 'given' : 'received' }
}

/** "10.06 18:26", "2024.05.18", "10월 6일" → YYYY-MM-DD. 연도가 없으면 오늘 이전의 가장 가까운 날짜 */
export function readDate(text: string, today: string): string | null {
  const m = DATE.exec(cleanText(text))
  if (!m) return null
  const mm = Number(m[2])
  const dd = Number(m[3])
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  let year = m[1] ? Number(m[1]) : Number(today.slice(0, 4))
  if (!m[1] && `${year}-${pad(mm)}-${pad(dd)}` > today) year -= 1
  return `${year}-${pad(mm)}-${pad(dd)}`
}

/** "사모회홍길동" → 이름 "홍길동" + 소속 "사모회" (제안). 2~4글자면 그대로 */
export function splitName(text: string): { name: string; group: string; flags: OcrFlag[] } {
  const t = cleanText(text)
  if (HANGUL_ONLY.test(t) && t.length >= 2 && t.length <= 4) return { name: t, group: '', flags: [] }
  if (HANGUL_ONLY.test(t) && t.length >= 5 && t.length <= 8) {
    return { name: t.slice(-3), group: t.slice(0, -3), flags: ['name-split'] }
  }
  return { name: t.slice(0, 20), group: '', flags: ['name-check'] }
}

/**
 * 줄 목록 → 내역.
 * 이름 줄마다 "같은 높이, 오른쪽"에 있는 금액 줄을 짝짓는다 (아래 줄의 잔액은 짝이 되지 않음).
 */
export function parseTransferLines(input: OcrLine[], today: string): { rows: OcrRow[]; unmatched: string[] } {
  // 한 줄에 "이름 100,000원"이 붙어 읽힌 경우 나누기
  const lines: OcrLine[] = []
  for (const l of input) {
    const text = cleanText(l.text)
    if (!text) continue
    const m = TRAILING_AMOUNT.exec(text)
    if (m && !readAmount(m[1]) && !readDate(m[1], today)) {
      const cut = l.left + ((l.right - l.left) * m[1].length) / text.length
      lines.push({ ...l, text: m[1], right: cut }, { ...l, text: m[2], left: cut })
    } else lines.push({ ...l, text })
  }

  const amounts = lines.filter((l) => readAmount(l.text))
  const dates = lines.filter((l) => readDate(l.text, today))
  const names = lines.filter(
    (l) => !readAmount(l.text) && !readDate(l.text, today) && !UI_WORDS.test(l.text.replace(/\s/g, '')) && /[가-힣A-Za-z]/.test(l.text),
  )

  const used = new Set<OcrLine>()
  const rows: OcrRow[] = []
  const unmatched: string[] = []
  for (const n of [...names].sort((a, b) => a.top - b.top)) {
    const band = height(n) * 0.7
    const candidates = amounts
      .filter((a) => !used.has(a) && a.left >= n.left && Math.abs(center(a) - center(n)) <= band + height(a) * 0.3)
      .sort((a, b) => Math.abs(center(a) - center(n)) - Math.abs(center(b) - center(n)))
    const a = candidates[0]
    if (!a) {
      unmatched.push(n.text)
      continue
    }
    used.add(a)
    const amt = readAmount(a.text)!
    const dateLine = dates.filter((d) => d.bottom <= n.top + height(n) * 0.5).sort((x, y) => y.bottom - x.bottom)[0]
    const { name, group, flags } = splitName(n.text)
    rows.push({
      key: `${Math.round(n.top)}-${Math.round(n.left)}`,
      name,
      group,
      amount: amt.amount,
      direction: amt.direction,
      date: dateLine ? readDate(dateLine.text, today) : null,
      raw: `${n.text} ${a.text}`,
      box: { left: Math.min(n.left, a.left), top: Math.min(n.top, a.top), right: Math.max(n.right, a.right), bottom: Math.max(n.bottom, a.bottom) },
      flags: amt.amount % 1000 !== 0 ? [...flags, 'amount-check'] : flags,
    })
  }
  return { rows, unmatched }
}
