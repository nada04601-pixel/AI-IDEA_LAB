export type Mood = 1 | 2 | 3 | 4 | 5

export interface Entry {
  id: string
  date: string // YYYY-MM-DD
  time: string // HH:mm
  mood: Mood
  memo: string
  tags: string[]
  createdAt: number
  updatedAt: number
}

/** screens.md 4-3 기분 5단계 */
export const MOODS: { value: Mood; emoji: string; label: string; color: string }[] = [
  { value: 1, emoji: '😞', label: '아주 힘듦', color: 'var(--mood-1)' },
  { value: 2, emoji: '🙁', label: '힘듦', color: 'var(--mood-2)' },
  { value: 3, emoji: '😐', label: '보통', color: 'var(--mood-3)' },
  { value: 4, emoji: '🙂', label: '괜찮음', color: 'var(--mood-4)' },
  { value: 5, emoji: '😊', label: '좋음', color: 'var(--mood-5)' },
]

export const TAGS = ['잠 못 잠', '잘 잠', '식사 거름', '사람 만남', '외출함', '운동함'] as const

export const MEMO_MAX = 100

export function moodInfo(mood: number) {
  return MOODS[Math.min(5, Math.max(1, Math.round(mood))) - 1]
}
