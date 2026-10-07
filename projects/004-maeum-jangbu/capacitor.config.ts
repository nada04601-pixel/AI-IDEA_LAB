import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'kr.co.novalabs.maeumjangbu',
  appName: '마음장부',
  webDir: 'dist',
  plugins: {
    LocalNotifications: {
      smallIcon: 'ic_stat_notify',
      iconColor: '#8C6A4F',
    },
  },
  android: {
    // 기록은 기기에만 저장. 인터넷 권한 없음 (tech-stack.md 1-1)
    allowMixedContent: false,
  },
}

export default config
