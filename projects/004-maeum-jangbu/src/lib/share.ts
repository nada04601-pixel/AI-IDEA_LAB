import { Directory, Encoding, Filesystem } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'
import { isNativeApp } from './platform'

export type ShareResult = 'shared' | 'canceled'

/**
 * 파일을 만들어 내보낸다 (tech-stack.md 5-4, 003 backupExport.ts 방식).
 * - 앱: 임시 폴더에 쓰고 공유 창. 저장할 곳(카카오톡 나에게, 드라이브, 이메일, 내 파일)은 사용자가 고른다.
 * - 웹: 다운로드.
 * 앱은 인터넷 권한이 없으므로 스스로 파일을 어디에도 보내지 않는다.
 */
export async function shareTextFile(name: string, text: string, mime: string, title: string): Promise<ShareResult> {
  if (!isNativeApp) {
    const blob = new Blob([text], { type: mime })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 1000)
    return 'shared'
  }
  const prefix = name.split('_').slice(0, 2).join('_')
  try {
    const { files } = await Filesystem.readdir({ path: '', directory: Directory.Cache })
    await Promise.all(
      files.filter((f) => f.name.startsWith(prefix)).map((f) => Filesystem.deleteFile({ path: f.name, directory: Directory.Cache })),
    )
  } catch {
    /* 이전 임시 파일 정리 실패는 무시 */
  }
  const { uri } = await Filesystem.writeFile({ path: name, data: text, directory: Directory.Cache, encoding: Encoding.UTF8 })
  try {
    await Share.share({ title, files: [uri], dialogTitle: '저장하거나 보낼 곳을 고르세요' })
  } catch (e) {
    if (/cancel/i.test(String((e as Error)?.message ?? e))) return 'canceled'
    throw e
  }
  return 'shared'
}
