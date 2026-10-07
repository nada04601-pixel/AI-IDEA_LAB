import { Capacitor } from '@capacitor/core'

/** Capacitor 안드로이드 앱 안에서 실행 중인지 */
export const isNativeApp = Capacitor.isNativePlatform()
