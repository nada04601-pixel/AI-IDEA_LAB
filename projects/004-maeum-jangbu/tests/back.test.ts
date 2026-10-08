import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'
import { handleBack, onBack } from '../src/lib/back'
import { toastText } from '../src/lib/toast'

/** 안드로이드 뒤로가기: 열린 창 닫기 → 이전 화면 → 홈 → 홈에서 두 번 눌러 종료 */
function fakeRouter(path: string) {
  const r = {
    currentRoute: { value: { path } },
    back: vi.fn(),
    replace: vi.fn(),
  }
  return r as unknown as Router & { back: ReturnType<typeof vi.fn>; replace: ReturnType<typeof vi.fn> }
}

beforeEach(() => {
  vi.stubGlobal('window', { history: { state: { back: '/people' } } })
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-08T00:00:00Z'))
})

describe('뒤로가기', () => {
  it('열린 창이 있으면 그 창만 닫는다', () => {
    const exit = vi.fn()
    const router = fakeRouter('/people/abc')
    const off = onBack(() => true)
    handleBack(router, exit)
    off()
    expect(router.back).not.toHaveBeenCalled()
    expect(exit).not.toHaveBeenCalled()
  })

  it('처리하지 않은 창은 건너뛴다', () => {
    const router = fakeRouter('/people/abc')
    const off = onBack(() => false)
    handleBack(router, vi.fn())
    off()
    expect(router.back).toHaveBeenCalledOnce()
  })

  it('하위 화면은 이전 화면으로, 이전 기록이 없으면 홈으로', () => {
    const router = fakeRouter('/records/new')
    handleBack(router, vi.fn())
    expect(router.back).toHaveBeenCalledOnce()

    vi.stubGlobal('window', { history: { state: null } })
    const router2 = fakeRouter('/records/new')
    handleBack(router2, vi.fn())
    expect(router2.replace).toHaveBeenCalledWith('/')
  })

  it('다른 탭에서는 홈으로 간다', () => {
    const router = fakeRouter('/settings')
    const exit = vi.fn()
    handleBack(router, exit)
    expect(router.replace).toHaveBeenCalledWith('/')
    expect(exit).not.toHaveBeenCalled()
  })

  it('홈에서는 2초 안에 두 번 눌러야 종료', () => {
    const router = fakeRouter('/')
    const exit = vi.fn()
    handleBack(router, exit)
    expect(exit).not.toHaveBeenCalled()
    expect(toastText.value).toBe('한 번 더 누르면 종료돼요')
    vi.advanceTimersByTime(2500)
    handleBack(router, exit)
    expect(exit).not.toHaveBeenCalled()
    vi.advanceTimersByTime(500)
    handleBack(router, exit)
    expect(exit).toHaveBeenCalledOnce()
  })
})
