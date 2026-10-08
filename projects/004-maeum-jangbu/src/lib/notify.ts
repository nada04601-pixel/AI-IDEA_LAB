import { LocalNotifications } from '@capacitor/local-notifications'
import { CHANGED_EVENT, db, getSetting, setSetting } from './db'
import { isNativeApp } from './platform'
import { DEFAULT_NOTIFY, allNotificationIds, planNotifications, type NotifySettings } from './notifySchedule'

/** 알림은 안드로이드 앱에서만 (기기 내 예약, 서버 없음) */
export const notifySupported = isNativeApp

export async function getNotifySettings(): Promise<NotifySettings> {
  return { ...DEFAULT_NOTIFY, ...(await getSetting<Partial<NotifySettings>>('notify', {})) }
}

export async function saveNotifySettings(patch: Partial<NotifySettings>) {
  await setSetting('notify', { ...(await getNotifySettings()), ...patch })
  await syncNotifications()
}

/** 설정·행사·백업 상태에 맞춰 예약을 다시 만든다 */
export async function syncNotifications(): Promise<void> {
  if (!notifySupported) return
  try {
    await LocalNotifications.cancel({ notifications: allNotificationIds().map((id) => ({ id })) })
    const perm = await LocalNotifications.checkPermissions()
    if (perm.display !== 'granted') return
    const plan = planNotifications(new Date(), await db.events.toArray(), await getNotifySettings(), {
      lastBackupAt: await getSetting<number | null>('lastBackupAt', null),
      pendingSince: await getSetting<number | null>('pendingSince', null),
      changes: await getSetting('changesSinceBackup', 0),
    })
    if (!plan.length) return
    await LocalNotifications.schedule({
      notifications: plan.map((p) => ({
        id: p.id,
        title: p.title,
        body: p.body,
        schedule: { at: p.at, allowWhileIdle: true },
        // 정확한 시각 알람을 쓰지 않는다: 쓰면 Android 12+에서 예약할 때마다 "알람 및 리마인더" 설정 화면이 열리고,
        // Play 정책상 정확한 알람 권한도 필요하다. 하루 전 오전 9시 알림은 몇 분 늦어도 괜찮다.
        isExactNotification: false,
        smallIcon: 'ic_stat_notify',
        autoCancel: true,
        extra: { route: p.route },
      })),
    })
  } catch (e) {
    // 알림 실패가 기록 기능을 막아서는 안 된다
    console.warn('알림 예약 실패', e)
  }
}

/**
 * 알림 권한 요청. 처음으로 상대 행사 알림을 켤 때 부른다 (screens.md S-01: 첫 실행에 묻지 않음).
 * 웹에서는 항상 false.
 */
export async function ensureNotifyPermission(): Promise<boolean> {
  if (!notifySupported) return false
  let perm = await LocalNotifications.checkPermissions()
  if (perm.display !== 'granted') perm = await LocalNotifications.requestPermissions()
  return perm.display === 'granted'
}

let timer: ReturnType<typeof setTimeout> | undefined
/** 앱 시작 시 한 번: 기록이 바뀔 때마다 예약 갱신, 알림을 누르면 해당 화면으로 */
export function initNotifications(go: (route: string) => void) {
  if (!notifySupported) return
  window.addEventListener(CHANGED_EVENT, () => {
    clearTimeout(timer)
    timer = setTimeout(() => void syncNotifications(), 800)
  })
  void LocalNotifications.addListener('localNotificationActionPerformed', (a) => {
    const route = a.notification.extra?.route
    if (typeof route === 'string') go(route)
  })
  void syncNotifications()
}
