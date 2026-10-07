/** 데이터 구조 (tech-stack.md 2장) */

export type Relation = 'family' | 'relative' | 'friend' | 'work' | 'acquaintance' | 'other'
export type EventOwner = 'mine' | 'theirs'
export type EventType = 'wedding' | 'funeral' | 'firstBirthday' | 'birthday' | 'opening' | 'other'
export type Direction = 'received' | 'given'
export type Method = 'cash' | 'transfer' | 'flower' | 'gift' | 'other'
export type Source = 'manual' | 'ocr' | 'import'

export interface Person {
  id: string
  name: string
  relation: Relation
  /** 소속·설명 (예: "대학 동기", "○○회사") — 동명이인 구분용 */
  group: string
  memo: string
  createdAt: number
  updatedAt: number
}

export interface LedgerEvent {
  id: string
  owner: EventOwner
  /** 상대 행사일 때 대상 사람 */
  personId: string | null
  type: EventType
  /** 직접 입력한 행사 종류 (type이 'other'일 때, 예: "칠순", "집들이"). 예전 데이터에는 없을 수 있다 */
  customType?: string
  title: string
  /** YYYY-MM-DD */
  date: string
  place: string
  /** D-day 알림 */
  remind: boolean
  /** 홈의 "기록이 비어 있는 경조사"에서 뺌 ([기록 안 함], screens.md S-02) */
  noRecordNeeded: boolean
  createdAt: number
  updatedAt: number
}

export interface LedgerRecord {
  id: string
  eventId: string
  personId: string
  direction: Direction
  /** 원 단위 정수. 화환·선물처럼 금액이 없으면 0 */
  amount: number
  method: Method
  attended: boolean | null
  /** 감사 인사 완료 */
  thanked: boolean
  memo: string
  source: Source
  createdAt: number
  updatedAt: number
}

export interface LedgerData {
  people: Person[]
  events: LedgerEvent[]
  records: LedgerRecord[]
}

export const RELATIONS: { value: Relation; label: string }[] = [
  { value: 'family', label: '가족' },
  { value: 'relative', label: '친척' },
  { value: 'friend', label: '친구' },
  { value: 'work', label: '직장' },
  { value: 'acquaintance', label: '지인' },
  { value: 'other', label: '기타' },
]

export const EVENT_TYPES: { value: EventType; label: string; icon: string }[] = [
  { value: 'wedding', label: '결혼', icon: '💍' },
  { value: 'funeral', label: '장례', icon: '🕊' },
  { value: 'firstBirthday', label: '돌잔치', icon: '🎂' },
  { value: 'birthday', label: '생신', icon: '🎉' },
  { value: 'opening', label: '개업', icon: '🏪' },
  { value: 'other', label: '기타', icon: '📌' },
]

export const METHODS: { value: Method; label: string }[] = [
  { value: 'cash', label: '현금' },
  { value: 'transfer', label: '계좌이체' },
  { value: 'flower', label: '화환' },
  { value: 'gift', label: '선물' },
  { value: 'other', label: '기타' },
]

export const relationLabel = (r: Relation) => RELATIONS.find((x) => x.value === r)?.label ?? '기타'
export const eventTypeLabel = (t: EventType) => EVENT_TYPES.find((x) => x.value === t)?.label ?? '기타'
/** 행사 종류 표시: 직접 입력한 종류가 있으면 그것 */
export const eventKindLabel = (e: Pick<LedgerEvent, 'type' | 'customType'>) =>
  e.type === 'other' && e.customType?.trim() ? e.customType.trim() : eventTypeLabel(e.type)
export const CUSTOM_TYPE_MAX = 20
export const eventTypeIcon = (t: EventType) => EVENT_TYPES.find((x) => x.value === t)?.icon ?? '📌'
export const methodLabel = (m: Method) => METHODS.find((x) => x.value === m)?.label ?? '기타'
export const directionLabel = (d: Direction) => (d === 'received' ? '받음' : '보냄')

/** 새 행사의 기본 제목: "내 결혼식", "김민수 결혼식" */
export function defaultEventTitle(owner: EventOwner, type: EventType, personName?: string, customType?: string): string {
  const names: Record<EventType, string> = {
    wedding: '결혼식', funeral: '장례', firstBirthday: '돌잔치', birthday: '생신', opening: '개업', other: customType?.trim() || '경조사',
  }
  return owner === 'mine' ? `내 ${names[type]}` : `${personName ?? ''} ${names[type]}`.trim()
}

export const uuid = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
