import { LocalNotifications } from '@capacitor/local-notifications'
import { entriesOn, getSetting, setSetting } from './db'
import { todayKey } from './date'
import { isNativeApp } from './platform'
import { DEFAULT_REMINDER_TIME, REMINDER_BODY, REMINDER_TITLE, allReminderIds, planReminders } from './reminderSchedule'

/**
 * 기록 알림. 안드로이드 앱에서만 동작한다 (기기 내 예약, 서버 없음).
 * 웹(PWA)은 정해진 시각 알림을 보낼 수 없다 (tech-stack.md 3).
 */
export const reminderSupported = isNativeApp

export interface ReminderState {
  enabled: boolean
  time: string
}

export async function getReminder(): Promise<ReminderState> {
  return {
    enabled: await getSetting('reminderEnabled', false),
    time: await getSetting('reminderTime', DEFAULT_REMINDER_TIME),
  }
}

async function cancelAll() {
  await LocalNotifications.cancel({ notifications: allReminderIds().map((id) => ({ id })) })
}

/** 설정과 오늘 기록 여부에 맞춰 예약을 다시 만든다. 앱 시작·기록 저장·설정 변경 때 호출. */
export async function syncReminder(): Promise<void> {
  if (!reminderSupported) return
  try {
    const { enabled, time } = await getReminder()
    await cancelAll()
    if (!enabled) return
    const perm = await LocalNotifications.checkPermissions()
    if (perm.display !== 'granted') return
    const recordedToday = (await entriesOn(todayKey())).length > 0
    const plan = planReminders(new Date(), time, recordedToday)
    if (!plan.length) return
    await LocalNotifications.schedule({
      notifications: plan.map((p) => ({
        id: p.id,
        title: REMINDER_TITLE,
        body: REMINDER_BODY,
        schedule: { at: p.at, allowWhileIdle: true },
        smallIcon: 'ic_stat_notify',
        autoCancel: true,
      })),
    })
  } catch (e) {
    // 알림 실패가 기록 기능을 막아서는 안 된다
    console.warn('알림 예약 실패', e)
  }
}

export type EnableResult = 'enabled' | 'denied'

/** 알림 켜기. 권한을 요청하고, 거부되면 설정은 꺼진 상태로 둔다. */
export async function enableReminder(time: string): Promise<EnableResult> {
  if (!reminderSupported) return 'denied'
  let perm = await LocalNotifications.checkPermissions()
  if (perm.display !== 'granted') perm = await LocalNotifications.requestPermissions()
  await setSetting('reminderTime', time)
  if (perm.display !== 'granted') {
    await setSetting('reminderEnabled', false)
    await syncReminder()
    return 'denied'
  }
  await setSetting('reminderEnabled', true)
  await syncReminder()
  return 'enabled'
}

export async function disableReminder(): Promise<void> {
  await setSetting('reminderEnabled', false)
  await syncReminder()
}

export async function setReminderTime(time: string): Promise<void> {
  await setSetting('reminderTime', time)
  await syncReminder()
}
