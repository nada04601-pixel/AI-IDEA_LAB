import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './style.css'
import { reload } from './lib/store'
import { initNotifications } from './lib/notify'
import { applyFontSize } from './lib/prefs'

void applyFontSize()
void reload()
createApp(App).use(router).mount('#app')

// 알림 예약 갱신 + 알림을 누르면 해당 화면으로 (앱 전용)
initNotifications((route) => void router.push(route))
