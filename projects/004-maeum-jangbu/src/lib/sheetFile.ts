/**
 * 엑셀(.xlsx)·CSV 파일 → 장부 데이터 (일괄 등록 화면과 가져오기·복원 화면이 같이 쓴다)
 * 엑셀 라이브러리는 필요할 때만 불러온다.
 */
import { parseCsv } from './sheet'
import { tableToData, type ImportResult } from './importData'

export const isSheetFile = (name: string) => /\.(xlsx|xls|csv)$/i.test(name)

export async function readSheetFile(file: File): Promise<ImportResult> {
  let table: unknown[][]
  if (/\.csv$/i.test(file.name)) table = parseCsv(await file.text())
  else {
    const { readWorkbook } = await import('./excel')
    table = await readWorkbook(await file.arrayBuffer())
  }
  const res = tableToData(table)
  if (!res.data.records.length) {
    throw new Error(
      res.issues.length
        ? `읽을 수 있는 줄이 없어요. (${res.issues[0].line}번째 줄: ${res.issues[0].reason})`
        : '가져올 내용이 없어요. 양식의 "전체 내역" 시트 둘째 줄부터 적었는지 확인해 주세요.',
    )
  }
  return res
}
