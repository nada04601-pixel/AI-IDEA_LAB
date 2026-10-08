import { registerPlugin } from '@capacitor/core'
import { isNativeApp } from './platform'

/** android/.../WebPrintPlugin.java */
interface WebPrintPlugin {
  print(options: { name: string }): Promise<void>
}
const WebPrint = registerPlugin<WebPrintPlugin>('WebPrint')

/**
 * 명단 인쇄 / PDF 저장.
 * - 웹: 브라우저 인쇄 창 (window.print)
 * - 앱: 안드로이드 기본 인쇄 화면 (WebView.createPrintDocumentAdapter)
 * 둘 다 인쇄 화면에서 "PDF로 저장"을 고르면 된다. 서버를 거치지 않는다.
 */
export async function printPage(name: string): Promise<void> {
  if (isNativeApp) await WebPrint.print({ name })
  else window.print()
}
