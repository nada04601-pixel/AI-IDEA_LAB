import { App } from '@capacitor/app'
import type { Router } from 'vue-router'
import { isNativeApp } from './platform'
import { showToast } from './toast'

/**
 * 안드로이드 뒤로가기 버튼 (2026-10-08)
 * 처리 순서: 열린 창 닫기(확인 창·기록 시트·선택 모드) → 이전 화면 → 다른 탭이면 홈 → 홈에서 두 번 누르면 종료
 * 플러그인 없이는 뒤로가기를 누르면 앱이 바로 종료됐다.
 */
type BackHandler = () => boolean
const handlers: BackHandler[] = []

/** 열려 있는 동안 뒤로가기를 먼저 받을 처리 등록. 처리했으면 true. 돌려받은 함수로 해제 */
export function onBack(fn: BackHandler): () => void {
  handlers.push(fn)
  return () => {
    const i = handlers.lastIndexOf(fn)
    if (i >= 0) handlers.splice(i, 1)
  }
}

const TAB_ROOTS = new Set(['/', '/people', '/events', '/settings'])
const EXIT_WINDOW_MS = 2000
let lastBackAt = 0

export function handleBack(router: Router, exit: () => void) {
  // 가장 나중에 열린 것부터
  for (let i = handlers.length - 1; i >= 0; i--) if (handlers[i]()) return
  const path = router.currentRoute.value.path
  const isRoot = TAB_ROOTS.has(path) || path === '/welcome'
  if (!isRoot) {
    if (window.history.state?.back) router.back()
    else router.replace('/')
    return
  }
  if (path !== '/' && path !== '/welcome') {
    router.replace('/')
    return
  }
  const now = Date.now()
  if (now - lastBackAt < EXIT_WINDOW_MS) exit()
  else {
    lastBackAt = now
    showToast('한 번 더 누르면 종료돼요', EXIT_WINDOW_MS)
  }
}

export function initBackButton(router: Router) {
  if (!isNativeApp) return
  void App.addListener('backButton', () => handleBack(router, () => void App.exitApp()))
}
