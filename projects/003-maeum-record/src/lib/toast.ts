import { ref } from 'vue'

export const toastText = ref<string | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined

/** 짧은 확인 메시지. 칭찬·점수 문구는 쓰지 않는다 (screens.md 5. 문구 기준) */
export function showToast(text: string, ms = 2000) {
  toastText.value = text
  clearTimeout(timer)
  timer = setTimeout(() => (toastText.value = null), ms)
}
