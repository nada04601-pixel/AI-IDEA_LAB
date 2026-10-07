import { describe, expect, it } from 'vitest'
import { addDays, dateRange, formatLong, formatTime, monthCells } from '../src/lib/date'
import { dayMood, summarize } from '../src/lib/summary'
import { mergeEntries, parseBackup, makeBackup } from '../src/lib/backup'
import type { Entry, Mood } from '../src/lib/mood'

let seq = 0
const e = (date: string, time: string, mood: Mood, memo = '', tags: string[] = []): Entry => ({
  id: `id-${++seq}`, date, time, mood, memo, tags, createdAt: 0, updatedAt: 0,
})

describe('date', () => {
  it('월·연도 경계를 넘어 날짜를 더한다', () => {
    expect(addDays('2026-10-01', -1)).toBe('2026-09-30')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
  it('기간은 양 끝을 포함한다', () => {
    expect(dateRange('2026-09-24', '2026-10-07')).toHaveLength(14)
  })
  it('한국어 표기', () => {
    expect(formatLong('2026-10-07')).toBe('10월 7일 수요일')
    expect(formatTime('14:10')).toBe('오후 2:10')
    expect(formatTime('00:05')).toBe('오전 12:05')
  })
  it('달력 앞쪽 빈칸', () => {
    const cells = monthCells(2026, 9) // 2026년 10월 1일은 목요일
    expect(cells.slice(0, 4)).toEqual([null, null, null, null])
    expect(cells[4]).toBe('2026-10-01')
    expect(cells.filter(Boolean)).toHaveLength(31)
  })
})

describe('summary', () => {
  it('하루 평균 기분은 반올림', () => {
    expect(dayMood([e('2026-10-01', '09:00', 2), e('2026-10-01', '21:00', 3)])).toBe(3)
    expect(dayMood([])).toBeNull()
  })

  it('기간 요약: 날짜 기준 분포, 태그, 최근 메모', () => {
    const entries = [
      e('2026-09-20', '10:00', 5, '기간 밖'),
      e('2026-10-01', '09:00', 1, '첫 메모', ['잠 못 잠']),
      e('2026-10-01', '22:00', 1, '', ['잠 못 잠', '식사 거름']),
      e('2026-10-03', '12:00', 4, '', ['외출함']),
      e('2026-10-06', '22:00', 2, '아무것도 하기 싫었다', ['잠 못 잠']),
    ]
    const s = summarize(entries, '2026-09-24', '2026-10-07')
    expect(s.totalDays).toBe(14)
    expect(s.recordedDays).toBe(3)
    expect(s.distribution).toEqual([1, 1, 0, 1, 0])
    expect(s.topTags[0]).toEqual({ tag: '잠 못 잠', count: 3 })
    expect(s.memos.map((m) => m.memo)).toEqual(['아무것도 하기 싫었다', '첫 메모'])
    expect(s.daily.find((d) => d.date === '2026-10-02')?.avg).toBeNull()
  })

  it('메모는 최대 5개', () => {
    const entries = Array.from({ length: 8 }, (_, i) => e(`2026-10-0${i + 1}`, '10:00', 3, `m${i}`))
    expect(summarize(entries, '2026-10-01', '2026-10-08').memos).toHaveLength(5)
  })
})

describe('backup', () => {
  it('합치기는 id 또는 같은 날짜·시각·기분을 중복으로 본다', () => {
    const a = e('2026-10-01', '09:00', 3)
    const b = e('2026-10-02', '09:00', 4)
    const sameAsA = { ...a, id: 'other-id' }
    const c = e('2026-10-03', '09:00', 2)
    const { result, added, skipped } = mergeEntries([a, b], [a, sameAsA, c], 'merge')
    expect(added).toBe(1)
    expect(skipped).toBe(2)
    expect(result).toHaveLength(3)
  })

  it('덮어쓰기', () => {
    const { result } = mergeEntries([e('2026-10-01', '09:00', 3)], [e('2026-10-05', '09:00', 1)], 'replace')
    expect(result.map((x) => x.date)).toEqual(['2026-10-05'])
  })

  it('왕복 및 잘못된 파일 거부', () => {
    const data = makeBackup([e('2026-10-01', '09:00', 3, 'x')], '하고 싶은 말')
    expect(parseBackup(JSON.stringify(data)).entries).toHaveLength(1)
    expect(() => parseBackup('not json')).toThrow('읽을 수 없어요')
    expect(() => parseBackup('{"entries":[]}')).toThrow('백업 파일이 아니에요')
    const bad = { ...data, entries: [{ ...data.entries[0], mood: 9 }] }
    expect(parseBackup(JSON.stringify(bad)).entries).toHaveLength(0)
  })
})

import { ID_BASE, parseTime, planReminders } from '../src/lib/reminderSchedule'

describe('reminder schedule', () => {
  const at = (s: string) => new Date(s) // 로컬 시간대 기준

  it('오늘 아직 기록 안 했고 시각 전이면 오늘부터', () => {
    const plan = planReminders(at('2026-10-07T13:00:00'), '21:00', false, 3)
    expect(plan.map((p) => p.at.getDate())).toEqual([7, 8, 9])
    expect(plan[0].at.getHours()).toBe(21)
    expect(plan[0].id).toBe(ID_BASE)
  })

  it('오늘 이미 기록했으면 오늘은 건너뛴다', () => {
    const plan = planReminders(at('2026-10-07T13:00:00'), '21:00', true, 3)
    expect(plan.map((p) => p.at.getDate())).toEqual([8, 9])
  })

  it('알림 시각이 지났으면 내일부터', () => {
    const plan = planReminders(at('2026-10-07T21:30:00'), '21:00', false, 2)
    expect(plan.map((p) => p.at.getDate())).toEqual([8])
  })

  it('월말을 넘어간다', () => {
    const plan = planReminders(at('2026-10-30T08:00:00'), '07:30', true, 3)
    expect(plan.map((p) => `${p.at.getMonth() + 1}/${p.at.getDate()}`)).toEqual(['10/31', '11/1'])
  })

  it('하루 1개, id 중복 없음, 기본 30일', () => {
    const plan = planReminders(at('2026-10-07T08:00:00'), '09:00', false)
    expect(plan).toHaveLength(30)
    expect(new Set(plan.map((p) => p.id)).size).toBe(30)
  })

  it('잘못된 시각 거부', () => {
    expect(parseTime('7:05')).toEqual({ hour: 7, minute: 5 })
    expect(() => parseTime('24:00')).toThrow()
    expect(() => parseTime('abc')).toThrow()
  })
})
