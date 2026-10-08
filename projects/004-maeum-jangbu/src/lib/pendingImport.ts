import { shallowRef } from 'vue'
import type { ImportResult } from './importData'

/**
 * 일괄 등록 화면에서 읽은 파일을 가져오기·복원 화면(미리보기·합치기)으로 넘기는 자리.
 * 화면 사이에서 한 번만 쓰고 비운다 (저장하지 않음).
 */
export const pendingImport = shallowRef<{ fileName: string; result: ImportResult } | null>(null)

export function takePendingImport() {
  const v = pendingImport.value
  pendingImport.value = null
  return v
}
