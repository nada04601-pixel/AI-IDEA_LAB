import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'kr.co.novalabs.maeumrecord',
  appName: '마음기록',
  webDir: 'dist',
  android: {
    // 기록은 기기에만 저장. 외부로 데이터를 보내지 않으므로 별도 네트워크 설정 없음.
    allowMixedContent: false,
  },
}

export default config
