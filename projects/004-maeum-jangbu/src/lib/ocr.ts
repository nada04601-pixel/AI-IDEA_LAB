import { registerPlugin } from '@capacitor/core'
import { isNativeApp } from './platform'
import type { OcrLine } from './ocrParse'

/** android/.../TextRecognitionPlugin.java — 휴대폰 안에서 글자 인식 */
interface TextRecognitionPlugin {
  recognize(options: { base64: string }): Promise<{ width: number; height: number; lines: OcrLine[] }>
  deleteCaptures(): Promise<{ deleted: number }>
}
const native = registerPlugin<TextRecognitionPlugin>('TextRecognition')

export interface PreparedImage {
  /** 화면 표시·인식에 쓰는 줄인 사진 (data URL) */
  url: string
  width: number
  height: number
}

/** 사진을 긴 변 1600px 이하 JPEG로 줄인다 (인식 속도·메모리). 원본은 저장하지 않는다 */
export async function prepareImage(file: File, maxSide = 1600): Promise<PreparedImage> {
  const src = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = src
    await img.decode()
    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight))
    const width = Math.round(img.naturalWidth * scale)
    const height = Math.round(img.naturalHeight * scale)
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, width, height)
    ctx.drawImage(img, 0, 0, width, height)
    return { url: canvas.toDataURL('image/jpeg', 0.9), width, height }
  } finally {
    URL.revokeObjectURL(src)
  }
}

/** 브라우저 개발 서버에서 화면을 확인하기 위한 가짜 인식 결과 (가명). 앱·배포 빌드에서는 쓰지 않는다 */
async function devRecognize(img: PreparedImage): Promise<OcrLine[]> {
  const { DEV_SAMPLE_LINES, DEV_SAMPLE_SIZE } = await import('./ocrDevSample')
  const sx = img.width / DEV_SAMPLE_SIZE.width
  const sy = img.height / DEV_SAMPLE_SIZE.height
  return DEV_SAMPLE_LINES.map((l) => ({ text: l.text, left: l.left * sx, top: l.top * sy, right: l.right * sx, bottom: l.bottom * sy }))
}

const useMock = !isNativeApp && import.meta.env.DEV

/** 사진 인식은 안드로이드 앱에서만 */
export const ocrSupported = isNativeApp || useMock

/**
 * [촬영]으로 찍은 사진 지우기.
 * 앱 WebView(Capacitor)는 카메라 앱이 찍은 사진을 앱 전용 폴더(Pictures/JPEG_*.jpg)에 남긴다.
 * 사진은 저장하지 않는다는 약속(idea.md 3-2)을 지키기 위해 읽은 뒤·화면을 떠날 때 지운다.
 */
export async function deleteCapturedPhotos(): Promise<void> {
  if (!isNativeApp) return
  try {
    await native.deleteCaptures()
  } catch (e) {
    console.warn('촬영 사진 정리 실패', e)
  }
}

/** 줄인 사진 → 줄 단위 글자와 위치 (사진 좌표) */
export async function recognize(img: PreparedImage): Promise<OcrLine[]> {
  if (useMock) return devRecognize(img)
  const r = await native.recognize({ base64: img.url })
  // 플러그인은 받은 사진 크기 기준 좌표를 돌려준다. 혹시 크기가 다르면 맞춘다
  const sx = img.width / (r.width || img.width)
  const sy = img.height / (r.height || img.height)
  return r.lines.map((l) => ({ text: l.text, left: l.left * sx, top: l.top * sy, right: l.right * sx, bottom: l.bottom * sy }))
}
