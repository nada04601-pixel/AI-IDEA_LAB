import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './style.css'
import { syncReminder } from './lib/reminder'

createApp(App).use(router).mount('#app')

// 앱을 열 때마다 알림 일정을 다시 계산한다 (오늘 기록 여부, 30일치)
void syncReminder()
