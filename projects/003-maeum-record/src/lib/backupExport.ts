import { Directory, Encoding, Filesystem } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'
import { allEntries, getSetting, setSetting } from './db'
import { backupFileName, makeBackup } from './backup'
import { todayKey } from './date'
import { isNativeApp } from './platform'

export type ExportResult = { status: 'saved'; count: number } | { status: 'canceled' }

const FILE_PREFIX = '마음기록_백업_'

/**
 * 백업 파일 만들기.
 * - 앱: 임시 폴더에 파일을 쓰고 공유 창을 띄운다. 저장할 곳(내 파일, 드라이브 등)은 사용자가 직접 고른다.
 * - 웹: 파일 다운로드.
 * 앱은 인터넷 권한이 없으므로 스스로 파일을 어디에도 보내지 않는다.
 */
export async function exportBackup(): Promise<ExportResult> {
  const data = makeBackup(await allEntries(), await getSetting('visitNote', ''))
  const json = JSON.stringify(data, null, 2)
  const name = backupFileName(todayKey())

  if (isNativeApp) {
    // 이전에 만든 임시 백업 파일 정리
    try {
      const { files } = await Filesystem.readdir({ path: '', directory: Directory.Cache })
      await Promise.all(
        files.filter((f) => f.name.startsWith(FILE_PREFIX)).map((f) => Filesystem.deleteFile({ path: f.name, directory: Directory.Cache })),
      )
    } catch {
      /* 정리 실패는 무시 */
    }
    const { uri } = await Filesystem.writeFile({ path: name, data: json, directory: Directory.Cache, encoding: Encoding.UTF8 })
    try {
      await Share.share({ title: '마음기록 백업', files: [uri], dialogTitle: '백업 파일을 저장할 곳을 고르세요' })
    } catch (e) {
      // 사용자가 공유 창을 닫은 경우
      if (/cancel/i.test(String((e as Error)?.message ?? e))) return { status: 'canceled' }
      throw e
    }
  } else {
    const blob = new Blob([json], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name
    a.click()
    URL.revokeObjectURL(a.href)
  }

  await setSetting('lastBackupAt', Date.now())
  return { status: 'saved', count: data.entries.length }
}

export const getLastBackupAt = () => getSetting<number | null>('lastBackupAt', null)
