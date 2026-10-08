import { describe, expect, it } from 'vitest'
import { formatFull, formatSentence, formatShort, parseAmount } from '../src/lib/money'
import { addDays, daysBetween, ddayLabel } from '../src/lib/date'
import { diffShort, diffText, eventSummary, missingGiven, receivedFrom, searchPeople, totalsByPerson, totalsOf, upcomingTheirs } from '../src/lib/ledger'
import { backupStatus, findNameConflicts, makeBackupText, matchPeople, mergeData, openBackup, previewOf, readBackupFile } from '../src/lib/backup'
import { WrongPasswordError, decryptText, encryptText } from '../src/lib/crypto'
import { BACKUP_ID, DEFAULT_NOTIFY, EVENT_ID_BASE, planNotifications } from '../src/lib/notifySchedule'
import type { LedgerData, LedgerEvent, LedgerRecord, Person } from '../src/lib/types'

const person = (id: string, name: string, group = ''): Person => ({
  id, name, relation: 'friend', group, memo: '', createdAt: 1, updatedAt: 1,
})
const event = (id: string, owner: 'mine' | 'theirs', date: string, personId: string | null = null, extra: Partial<LedgerEvent> = {}): LedgerEvent => ({
  id, owner, personId, type: 'wedding', customType: '', title: owner === 'mine' ? '내 결혼식' : '결혼식', date, place: '', remind: true,
  noRecordNeeded: false, createdAt: 1, updatedAt: 1, ...extra,
})
const record = (id: string, eventId: string, personId: string, direction: 'received' | 'given', amount: number, extra: Partial<LedgerRecord> = {}): LedgerRecord => ({
  id, eventId, personId, direction, amount, method: 'cash', attended: true, thanked: false, memo: '', source: 'manual',
  createdAt: 1, updatedAt: 1, ...extra,
})

describe('금액 표기 (screens.md 4-3)', () => {
  it('목록·합계는 줄여 쓴다', () => {
    expect(formatShort(100000)).toBe('10만')
    expect(formatShort(50000)).toBe('5만')
    expect(formatShort(18450000)).toBe('1,845만')
    expect(formatShort(35000)).toBe('3만 5천')
    expect(formatShort(5000)).toBe('5천')
    expect(formatShort(123456)).toBe('123,456')
    expect(formatShort(0)).toBe('0')
  })
  it('입력 확인은 정확하게, 문장은 원을 붙인다', () => {
    expect(formatFull(100000)).toBe('100,000원')
    expect(formatSentence(100000)).toBe('10만원')
    expect(formatSentence(35000)).toBe('3만 5천원')
  })
  it('입력 문자열을 원 단위로 바꾼다', () => {
    expect(parseAmount('100,000')).toBe(100000)
    expect(parseAmount('100,000원')).toBe(100000)
    expect(parseAmount('10만')).toBe(100000)
    expect(parseAmount('10만원')).toBe(100000)
    expect(parseAmount('3만 5천')).toBe(35000)
    expect(parseAmount('3만5천원')).toBe(35000)
    expect(parseAmount('1.5만')).toBe(15000)
    expect(parseAmount('5천')).toBe(5000)
    expect(parseAmount('15', 'man')).toBe(150000)
    expect(parseAmount('')).toBeNull()
    expect(parseAmount('십만')).toBeNull()
    expect(parseAmount('만')).toBeNull()
  })
})

describe('날짜', () => {
  it('D-day 표시', () => {
    expect(ddayLabel('2026-11-21', '2026-11-18')).toBe('D-3')
    expect(ddayLabel('2026-11-21', '2026-11-21')).toBe('D-day')
    expect(ddayLabel('2026-11-21', '2026-11-23')).toBe('D+2')
    expect(daysBetween('2026-12-30', '2027-01-02')).toBe(3)
    expect(addDays('2026-02-28', 1)).toBe('2026-03-01')
  })
})

describe('장부 계산', () => {
  const people = [person('p1', '김민수', '대학 동기'), person('p2', '박지영', '○○회사'), person('p3', '김민지')]
  const events = [
    event('mine1', 'mine', '2024-05-18'),
    event('t1', 'theirs', '2026-11-21', 'p1'),
    event('t2', 'theirs', '2026-09-14', 'p2'),
    event('t3', 'theirs', '2026-08-01', 'p3', { noRecordNeeded: true }),
    event('t4', 'theirs', '2026-10-02', 'p3'),
  ]
  const records = [
    record('r1', 'mine1', 'p1', 'received', 100000, { thanked: true }),
    record('r2', 'mine1', 'p2', 'received', 50000, { method: 'transfer' }),
    record('r3', 't1', 'p1', 'given', 100000),
    record('r4', 't4', 'p3', 'given', 50000),
    record('r5', 'mine1', 'p3', 'received', 0, { method: 'flower' }),
  ]

  it('사람별 합계와 차이 문구', () => {
    const map = totalsByPerson(records)
    expect(map.get('p1')).toEqual({ received: 100000, given: 100000, receivedCount: 1, givenCount: 1 })
    expect(diffText(map.get('p1')!)).toBe('주고받은 금액이 같아요')
    expect(diffText(map.get('p2')!)).toBe('받은 게 5만원 더 많아요')
    expect(diffShort(map.get('p2')!)).toBe('받은 게 5만 더')
    expect(diffText(map.get('p3')!)).toBe('보낸 게 5만원 더 많아요')
    expect(diffText(totalsOf([]))).toBeNull()
  })

  it('행사별 합계: 건수, 방식별, 감사 인사', () => {
    const s = eventSummary(records.filter((r) => r.eventId === 'mine1'))
    expect(s).toEqual({ count: 3, total: 150000, byMethod: { cash: 1, transfer: 1, flower: 1 }, thanked: 1 })
  })

  it('기록 참고: 그 사람에게 받은 기록만', () => {
    const ref = receivedFrom('p1', records, events)
    expect(ref).toHaveLength(1)
    expect(ref[0].event?.id).toBe('mine1')
    expect(receivedFrom('nobody', records, events)).toEqual([])
  })

  it('다가오는 경조사와 기록이 비어 있는 경조사', () => {
    expect(upcomingTheirs(events, '2026-10-07').map((e) => e.id)).toEqual(['t1'])
    // t2: 지남 + 보냄 없음 → 표시 / t3: 기록 안 함 → 제외 / t4: 보냄 있음 → 제외
    expect(missingGiven(events, records, '2026-10-07').map((e) => e.id)).toEqual(['t2'])
  })

  it('이름 검색: 앞부분 일치 먼저', () => {
    expect(searchPeople(people, '김민').map((p) => p.id)).toEqual(['p1', 'p3'])
    expect(searchPeople(people, '회사').map((p) => p.id)).toEqual(['p2'])
    expect(searchPeople(people, ' ')).toEqual([])
  })
})

describe('백업 암호화 (tech-stack.md 5-1)', () => {
  it('같은 비밀번호로 풀리고, 틀리면 WrongPasswordError', async () => {
    const enc = await encryptText('마음장부 비밀', '1234', 1000)
    expect(enc.data).not.toContain('마음장부')
    expect(await decryptText(enc, '1234')).toBe('마음장부 비밀')
    await expect(decryptText(enc, '9999')).rejects.toBeInstanceOf(WrongPasswordError)
  })
})

describe('백업 파일', () => {
  const data: LedgerData = {
    people: [person('p1', '김민수')],
    events: [event('e1', 'mine', '2024-05-18')],
    records: [record('r1', 'e1', 'p1', 'received', 100000)],
  }

  it('비밀번호 없는 백업 왕복', async () => {
    const text = await makeBackupText(data)
    const file = readBackupFile(text)
    expect(file.encrypted).toBe(false)
    expect(await openBackup(file)).toEqual(data)
  })

  it('비밀번호 백업 왕복', async () => {
    const text = await makeBackupText(data, 'pw')
    expect(text).not.toContain('김민수')
    const file = readBackupFile(text)
    expect(file.encrypted).toBe(true)
    await expect(openBackup(file, 'wrong')).rejects.toBeInstanceOf(WrongPasswordError)
    expect(await openBackup(file, 'pw')).toEqual(data)
  }, 20000)

  it('다른 파일·새 버전·손상된 항목', () => {
    expect(() => readBackupFile('not json')).toThrow('읽을 수 없어요')
    expect(() => readBackupFile('{"format":"other"}')).toThrow('백업 파일이 아니에요')
    expect(() => readBackupFile(JSON.stringify({ format: 'maeum-jangbu-backup', version: 99, encrypted: false, data }))).toThrow('업데이트')
    const broken = {
      format: 'maeum-jangbu-backup', version: 1, encrypted: false,
      data: { ...data, records: [...data.records, { id: 'x', eventId: 'none', personId: 'p1' }, null] },
    }
    const file = readBackupFile(JSON.stringify(broken))
    expect(file.encrypted || file.data.records.map((r) => r.id)).toEqual(['r1'])
  })

  it('미리보기', () => {
    expect(previewOf(data)).toEqual({ people: 1, events: 1, records: 1, from: '2024-05-18', to: '2024-05-18' })
  })
})

describe('행사 제목·종류 표시', () => {
  it('직접 입력한 종류로 기본 제목을 만든다', async () => {
    const { defaultEventTitle, eventKindLabel } = await import('../src/lib/types')
    expect(defaultEventTitle('mine', 'other', undefined, '칠순')).toBe('내 칠순')
    expect(defaultEventTitle('theirs', 'other', '김민수', ' 집들이 ')).toBe('김민수 집들이')
    expect(defaultEventTitle('theirs', 'other', '김민수', '')).toBe('김민수 경조사')
    expect(defaultEventTitle('mine', 'wedding')).toBe('내 결혼식')
    expect(eventKindLabel({ type: 'other', customType: '칠순' })).toBe('칠순')
    expect(eventKindLabel({ type: 'other' })).toBe('기타')
    expect(eventKindLabel({ type: 'wedding', customType: '무시됨' })).toBe('결혼')
  })

  it('같은 날 직접 입력한 종류가 다르면 다른 행사로 합친다', () => {
    const base: LedgerData = { people: [person('p1', '김민수')], events: [{ ...event('a', 'theirs', '2026-05-05', 'p1'), type: 'other', customType: '칠순' }], records: [] }
    const inc: LedgerData = { people: [person('p1', '김민수')], events: [{ ...event('b', 'theirs', '2026-05-05', 'p1'), type: 'other', customType: '집들이' }], records: [] }
    expect(mergeData(base, inc).added.events).toBe(1)
    const same: LedgerData = { ...inc, events: [{ ...inc.events[0], customType: '칠순' }] }
    expect(mergeData(base, same).added.events).toBe(0)
  })

  it('예전 백업(customType 없음)도 읽는다', async () => {
    const old = { format: 'maeum-jangbu-backup', version: 1, encrypted: false, data: { people: [person('p1', '김')], events: [{ ...event('e', 'mine', '2024-01-01'), customType: undefined }], records: [] } }
    const f = readBackupFile(JSON.stringify(old))
    expect(f.encrypted || f.data.events[0].customType).toBe('')
  })
})

describe('합치기 (tech-stack.md 5-2)', () => {
  const existing: LedgerData = {
    people: [person('p1', '김민수', '대학 동기'), person('p2', '박지영')],
    events: [event('e1', 'mine', '2024-05-18')],
    records: [record('r1', 'e1', 'p1', 'received', 100000)],
  }

  it('같은 id·같은 내용은 건너뛰고 새 기록만 더한다', () => {
    const incoming: LedgerData = {
      people: [person('p1', '김민수', '대학 동기'), person('p9', '이현우')],
      // 다른 기기에서 같은 날 같은 종류로 만든 내 결혼식 → 같은 행사로 본다
      events: [event('e9', 'mine', '2024-05-18')],
      records: [
        record('r1', 'e9', 'p1', 'received', 100000),
        record('r8', 'e9', 'p1', 'received', 100000), // id만 다르고 내용 같음 → 중복
        record('r9', 'e9', 'p9', 'received', 300000),
      ],
    }
    const { result, added, skippedRecords } = mergeData(existing, incoming)
    expect(added).toEqual({ people: 1, events: 0, records: 1 })
    expect(skippedRecords).toBe(2)
    expect(result.records.find((r) => r.id === 'r9')?.eventId).toBe('e1')
  })

  it('이름만 같은 사람은 자동으로 합치지 않고 확인 목록으로', () => {
    const incoming: LedgerData = {
      people: [person('q2', '박지영', '교회')],
      events: [event('t1', 'theirs', '2026-11-30', 'q2')],
      records: [record('x1', 't1', 'q2', 'given', 50000)],
    }
    const conflicts = findNameConflicts(existing, incoming)
    expect(conflicts.map((c) => [c.existing.id, c.incoming.id])).toEqual([['p2', 'q2']])

    // "다른 사람" → 따로 추가
    const separate = mergeData(existing, incoming)
    expect(separate.added.people).toBe(1)

    // 이름과 소속까지 같으면 묻지 않고 같은 사람으로 본다
    const exact = matchPeople(existing, { ...incoming, people: [person('q1', '김민수', '대학 동기')] })
    expect(exact).toEqual({ sameAs: { q1: 'p1' }, conflicts: [] })

    // "같은 사람" → 기존 사람으로 연결 (행사·내역의 사람도 바뀐다)
    const same = mergeData(existing, incoming, { q2: 'p2' })
    expect(same.added.people).toBe(0)
    expect(same.result.events.find((e) => e.id === 't1')?.personId).toBe('p2')
    expect(same.result.records.find((r) => r.id === 'x1')?.personId).toBe('p2')
  })
})

describe('백업 상태 (screens.md S-02)', () => {
  const DAY = 86_400_000
  const now = Date.UTC(2026, 9, 7)
  it('기록 없음 / 백업한 적 없음 / 30일 경과 / 최근 백업', () => {
    expect(backupStatus(false, null, 0, now).kind).toBe('empty')
    expect(backupStatus(true, null, 5, now).kind).toBe('never')
    expect(backupStatus(true, now - 32 * DAY, 48, now)).toEqual({ kind: 'overdue', days: 32, changes: 48 })
    // 30일이 지나도 그 사이 바뀐 기록이 없으면 알리지 않는다
    expect(backupStatus(true, now - 40 * DAY, 0, now).kind).toBe('ok')
    expect(backupStatus(true, now - 2 * DAY, 3, now).kind).toBe('ok')
  })
})

describe('알림 일정', () => {
  const now = new Date(2026, 9, 7, 12, 0)
  const events = [
    event('t1', 'theirs', '2026-11-21', 'p1', { title: '김민수 결혼식', place: '○○웨딩홀' }),
    event('t2', 'theirs', '2026-10-08', 'p2', { title: '내일 행사' }), // 하루 전 9시 = 오늘 9시 → 지남
    event('t3', 'theirs', '2026-12-01', 'p3', { remind: false }),
    event('m1', 'mine', '2026-12-05'),
  ]
  const noBackup = { lastBackupAt: null, pendingSince: null, changes: 0 }

  it('상대 행사 중 알림을 켠 것만, 하루 전 오전 9시', () => {
    const plan = planNotifications(now, events, DEFAULT_NOTIFY, noBackup)
    expect(plan).toHaveLength(1)
    expect(plan[0]).toMatchObject({ id: EVENT_ID_BASE, title: '내일 김민수 결혼식', body: '11/21(토) · ○○웨딩홀', route: '/events/t1' })
    expect(plan[0].at).toEqual(new Date(2026, 10, 20, 9, 0))
  })

  it('당일 알림 설정', () => {
    const plan = planNotifications(now, events, { ...DEFAULT_NOTIFY, daysBefore: 0, time: '08:30' }, noBackup)
    expect(plan.map((p) => p.title)).toEqual(['오늘 내일 행사', '오늘 김민수 결혼식'])
    expect(plan[0].at).toEqual(new Date(2026, 9, 8, 8, 30))
  })

  it('백업 알림: 마지막 백업 30일 뒤 저녁 8시, 바뀐 기록이 없으면 없음', () => {
    const last = new Date(2026, 9, 1, 10).getTime()
    const plan = planNotifications(now, [], DEFAULT_NOTIFY, { lastBackupAt: last, pendingSince: null, changes: 3 })
    expect(plan).toHaveLength(1)
    expect(plan[0]).toMatchObject({ id: BACKUP_ID, route: '/backup' })
    expect(plan[0].at).toEqual(new Date(2026, 9, 31, 20, 0))
    expect(planNotifications(now, [], DEFAULT_NOTIFY, { lastBackupAt: last, pendingSince: null, changes: 0 })).toEqual([])
  })

  it('이미 지났으면 사흘 뒤 한 번', () => {
    const last = new Date(2026, 7, 1).getTime()
    const plan = planNotifications(now, [], DEFAULT_NOTIFY, { lastBackupAt: last, pendingSince: null, changes: 1 })
    expect(plan[0].at).toEqual(new Date(2026, 9, 10, 20, 0))
  })
})
