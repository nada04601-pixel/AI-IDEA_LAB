import { createRouter, createWebHashHistory } from 'vue-router'
import { getSetting } from './lib/db'

const tab = { tab: true, add: true }

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/welcome', name: 'welcome', component: () => import('./pages/WelcomeView.vue'), meta: { bare: true } },
    { path: '/', name: 'home', component: () => import('./pages/HomeView.vue'), meta: tab },
    { path: '/people', name: 'people', component: () => import('./pages/PeopleView.vue'), meta: tab },
    { path: '/people/new', name: 'person-new', component: () => import('./pages/PersonEditView.vue'), meta: { title: '사람 추가' } },
    { path: '/contacts', name: 'contacts', component: () => import('./pages/ContactsImportView.vue'), meta: { title: '연락처에서 불러오기' } },
    { path: '/people/:id', name: 'person', component: () => import('./pages/PersonView.vue'), meta: { title: '사람' } },
    { path: '/people/:id/edit', name: 'person-edit', component: () => import('./pages/PersonEditView.vue'), meta: { title: '사람 편집' } },
    { path: '/events', name: 'events', component: () => import('./pages/EventsView.vue'), meta: tab },
    { path: '/events/new', name: 'event-new', component: () => import('./pages/EventEditView.vue'), meta: { title: '행사 추가' } },
    { path: '/events/:id', name: 'event', component: () => import('./pages/EventView.vue'), meta: { title: '행사' } },
    { path: '/events/:id/edit', name: 'event-edit', component: () => import('./pages/EventEditView.vue'), meta: { title: '행사 편집' } },
    { path: '/record', name: 'record', component: () => import('./pages/RecordFormView.vue'), meta: { title: '기록하기' } },
    { path: '/quick', name: 'quick', component: () => import('./pages/QuickEntryView.vue'), meta: { title: '명단 빠르게 입력' } },
    { path: '/records', name: 'records', component: () => import('./pages/RecordsView.vue'), meta: { title: '전체 기록' } },
    { path: '/search', name: 'search', component: () => import('./pages/SearchView.vue'), meta: { title: '검색' } },
    { path: '/ocr', name: 'ocr', component: () => import('./pages/OcrView.vue'), meta: { title: '사진으로 등록' } },
    { path: '/export', name: 'export', component: () => import('./pages/ExportView.vue'), meta: { title: '엑셀·CSV·PDF 내보내기' } },
    { path: '/events/:id/print', name: 'event-print', component: () => import('./pages/PrintRosterView.vue'), meta: { title: '명단 PDF' } },
    { path: '/backup', name: 'backup', component: () => import('./pages/BackupView.vue'), meta: { title: '내보내기·백업' } },
    { path: '/restore', name: 'restore', component: () => import('./pages/RestoreView.vue'), meta: { title: '가져오기·복원' } },
    { path: '/privacy', name: 'privacy', component: () => import('./pages/PrivacyView.vue'), meta: { title: '개인정보처리방침' } },
    { path: '/move', name: 'move', component: () => import('./pages/MoveGuideView.vue'), meta: { title: '새 휴대폰으로 옮기기' } },
    { path: '/settings', name: 'settings', component: () => import('./pages/SettingsView.vue'), meta: { tab: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

let onboarded: boolean | null = null
export const markOnboarded = () => { onboarded = true }
export const resetOnboarded = () => { onboarded = false }

router.beforeEach(async (to) => {
  if (to.name === 'welcome') return true
  if (onboarded === null) onboarded = await getSetting('onboardingDone', false)
  if (!onboarded) return { name: 'welcome' }
  return true
})
