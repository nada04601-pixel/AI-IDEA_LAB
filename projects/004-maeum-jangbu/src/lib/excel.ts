/**
 * 엑셀 만들기·읽기 (ExcelJS) — tech-stack.md 5-3
 * ExcelJS는 용량이 커서 이 파일은 내보내기·가져오기 화면에서만 동적으로 불러온다.
 */
import ExcelJS from 'exceljs'
import { PERSON_COLUMNS, RECORD_COLUMNS, ROSTER_COLUMNS, personRows, recordRows, rosters, sheetName, type Row } from './sheet'
import type { LedgerData } from './types'
import { formatDot } from './date'

const MONEY = '#,##0'
const HEADER_FILL: ExcelJS.Fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF1E8DE' } }

function addTable(ws: ExcelJS.Worksheet, header: readonly string[], rows: Row[], widths: number[], moneyCols: number[], startRow = 1) {
  const head = ws.getRow(startRow)
  head.values = [...header]
  head.font = { bold: true }
  head.fill = HEADER_FILL
  head.alignment = { vertical: 'middle' }
  head.height = 20
  rows.forEach((r, i) => (ws.getRow(startRow + 1 + i).values = r))
  widths.forEach((w, i) => (ws.getColumn(i + 1).width = w))
  // 금액은 숫자로 저장하고 서식만 입힌다 → 엑셀에서 바로 합계·정렬 가능
  for (const c of moneyCols) ws.getColumn(c).numFmt = MONEY
  ws.views = [{ state: 'frozen', ySplit: startRow }]
  if (rows.length) ws.autoFilter = { from: { row: startRow, column: 1 }, to: { row: startRow + rows.length, column: header.length } }
}

export async function buildWorkbook(data: LedgerData, title: string): Promise<Uint8Array> {
  const wb = new ExcelJS.Workbook()
  wb.creator = '마음장부'
  wb.created = new Date()
  const used = new Set<string>()

  // ① 전체 내역 (= 가져오기 양식)
  const all = wb.addWorksheet(sheetName('전체 내역', used))
  addTable(all, RECORD_COLUMNS, recordRows(data), [12, 18, 9, 10, 7, 14, 9, 12, 9, 7, 9, 20], [8])

  // ② 사람별 장부
  const ppl = wb.addWorksheet(sheetName('사람별 장부', used))
  addTable(ppl, PERSON_COLUMNS, personRows(data), [10, 7, 14, 12, 12, 14, 13], [4, 5, 6])

  // ③ 행사별 명단 (내 행사마다 1시트, 맨 위에 행사 정보, 아래에 합계 행)
  for (const r of rosters(data)) {
    const ws = wb.addWorksheet(sheetName(`${r.event.title} ${r.event.date.slice(2, 4)}${r.event.date.slice(5, 7)}${r.event.date.slice(8)}`, used))
    ws.getCell('A1').value = r.event.title
    ws.getCell('A1').font = { bold: true, size: 14 }
    ws.getCell('A2').value = `${formatDot(r.event.date)}${r.event.place ? ` · ${r.event.place}` : ''} · ${r.rows.length}명`
    addTable(ws, ROSTER_COLUMNS, r.rows, [6, 10, 7, 14, 12, 9, 7, 9], [5], 4)
    const totalRow = ws.getRow(5 + r.rows.length)
    totalRow.values = ['', '합계', '', '', r.total]
    totalRow.font = { bold: true }
    totalRow.getCell(5).numFmt = MONEY
    ws.views = [{ state: 'frozen', ySplit: 4 }]
  }

  wb.title = title
  return new Uint8Array(await wb.xlsx.writeBuffer())
}

/** 엑셀 파일의 표 읽기: "전체 내역" 시트가 있으면 그것, 없으면 첫 시트 */
export async function readWorkbook(buf: ArrayBuffer): Promise<unknown[][]> {
  const wb = new ExcelJS.Workbook()
  try {
    await wb.xlsx.load(buf)
  } catch {
    throw new Error('엑셀 파일을 읽을 수 없어요. .xlsx 형식인지 확인해 주세요. (오래된 .xls는 엑셀에서 .xlsx로 다시 저장해 주세요)')
  }
  const ws = wb.getWorksheet('전체 내역') ?? wb.worksheets[0]
  if (!ws) throw new Error('엑셀 파일에 시트가 없어요.')
  const out: unknown[][] = []
  ws.eachRow({ includeEmpty: false }, (row) => {
    const vals: unknown[] = []
    for (let c = 1; c <= ws.columnCount; c++) {
      let v: unknown = row.getCell(c).value
      // 수식 → 결과값, 서식 있는 글자 → 글자만
      if (v && typeof v === 'object' && !(v instanceof Date)) {
        const o = v as { result?: unknown; richText?: { text: string }[]; text?: string }
        v = o.result ?? (o.richText ? o.richText.map((t) => t.text).join('') : (o.text ?? ''))
      }
      vals.push(v ?? '')
    }
    out.push(vals)
  })
  return out
}
