import { createRouter, createWebHashHistory } from 'vue-router'
import { getSetting } from './lib/db'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./pages/HomeView.vue'), meta: { tab: true } },
    { path: '/welcome', name: 'welcome', component: () => import('./pages/WelcomeView.vue'), meta: { bare: true } },
    { path: '/calendar', name: 'calendar', component: () => import('./pages/CalendarView.vue'), meta: { tab: true } },
    { path: '/visit', name: 'visit', component: () => import('./pages/VisitPrepView.vue'), meta: { tab: true } },
    { path: '/report', name: 'report', component: () => import('./pages/ReportView.vue'), meta: { title: '리포트' } },
    { path: '/guides', name: 'guides', component: () => import('./pages/GuideListView.vue'), meta: { tab: true } },
    { path: '/guides/:slug', name: 'guide', component: () => import('./pages/GuideDetailView.vue'), meta: { title: '가이드' } },
    { path: '/help', name: 'help', component: () => import('./pages/HelpView.vue'), meta: { title: '도움받을 곳' } },
    { path: '/settings', name: 'settings', component: () => import('./pages/SettingsView.vue'), meta: { title: '설정' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

let onboarded: boolean | null = null
export const markOnboarded = () => { onboarded = true }
export const resetOnboarded = () => { onboarded = false }

router.beforeEach(async (to) => {
  // 도움받을 곳은 어떤 상태에서든 열 수 있어야 한다 (screens.md S-08)
  if (to.name === 'help' || to.name === 'welcome') return true
  if (onboarded === null) onboarded = await getSetting('onboardingDone', false)
  if (!onboarded) return { name: 'welcome' }
  return true
})
