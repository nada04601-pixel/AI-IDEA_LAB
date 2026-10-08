/**
 * 엑셀 만들기·읽기 (ExcelJS) — tech-stack.md 5-3
 * ExcelJS는 용량이 커서 이 파일은 내보내기·가져오기 화면에서만 동적으로 불러온다.
 */
import ExcelJS from 'exceljs'
import { PERSON_COLUMNS, RECORD_COLUMNS, ROSTER_COLUMNS, personRows, recordRows, rosters, sheetName, type Row } from './sheet'
import { EVENT_TYPES, METHODS, RELATIONS, type LedgerData } from './types'
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

/** 일괄 등록 양식에 미리 넣어 두는 빈 줄 수 (드롭다운·서식이 적용되는 범위) */
export const TEMPLATE_ROWS = 500

const REQUIRED_FILL: ExcelJS.Fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF6D7B0' } }

/** 열별 고르기 목록 (엑셀 드롭다운). 행사 종류는 목록에 없는 말도 쓸 수 있다 (직접 입력, 예: 칠순) */
function templateLists() {
  return new Map<string, string[]>([
    ['행사 종류', EVENT_TYPES.map((t) => t.label)],
    ['관계', RELATIONS.map((r) => r.label)],
    ['받음/보냄', ['받음', '보냄']],
    ['방식', METHODS.map((m) => m.label)],
    ['참석', ['참석', '불참']],
    ['감사 인사', ['완료']],
  ])
}

/**
 * 일괄 등록용 빈 엑셀 양식 (idea.md 3-3, 2026-10-08)
 * - "전체 내역" 시트: 내보내기와 같은 열. 필수 열(날짜·이름·금액) 강조, 고르기 목록, 날짜·금액 서식
 * - "작성 방법" 시트: 규칙과 예시 (가져오기는 "전체 내역" 시트만 읽으므로 예시가 등록되지 않는다)
 */
export async function buildTemplate(): Promise<Uint8Array> {
  const wb = new ExcelJS.Workbook()
  wb.creator = '마음장부'
  wb.created = new Date()

  const ws = wb.addWorksheet('전체 내역')
  addTable(ws, RECORD_COLUMNS, [], [12, 18, 10, 10, 8, 14, 10, 12, 10, 8, 9, 20], [8])
  const required = new Set(['날짜', '이름', '금액'])
  const lists = templateLists()
  RECORD_COLUMNS.forEach((name, i) => {
    const col = i + 1
    const head = ws.getRow(1).getCell(col)
    if (required.has(name)) {
      head.fill = REQUIRED_FILL
      head.value = `${name} *`
      head.note = '필수'
    }
    if (name === '날짜') ws.getColumn(col).numFmt = 'yyyy-mm-dd'
    const list = lists.get(name)
    if (!list) return
    for (let r = 2; r <= TEMPLATE_ROWS + 1; r++) {
      ws.getCell(r, col).dataValidation = {
        type: 'list',
        allowBlank: true,
        formulae: [`"${list.join(',')}"`],
        // 행사 종류는 목록 밖의 말(칠순, 집들이 등)도 허용
        showErrorMessage: name !== '행사 종류',
        errorStyle: 'stop',
        errorTitle: '목록에서 골라 주세요',
        error: `${list.join(', ')} 중에서 골라 주세요`,
      }
    }
  })

  const guide = wb.addWorksheet('작성 방법')
  guide.getColumn(1).width = 100
  const lines: [string, Partial<ExcelJS.Font>?][] = [
    ['마음장부 일괄 등록 양식', { bold: true, size: 14 }],
    [''],
    ['"전체 내역" 시트에 한 줄에 한 사람씩 적은 뒤, 앱의 [엑셀·CSV로 한꺼번에 등록]에서 이 파일을 올리세요.'],
    ['이 "작성 방법" 시트는 등록되지 않아요.'],
    [''],
    ['필수: 날짜 · 이름 · 금액 (주황색 칸)', { bold: true }],
    ['· 날짜: 2024-05-18, 2024.05.18, 2024년 5월 18일 모두 돼요'],
    ['· 금액: 100000, 100,000, 10만, 10만원 모두 돼요. 화환·선물처럼 금액이 없으면 0'],
    [''],
    ['비워도 되는 칸', { bold: true }],
    ['· 받음/보냄: 비우면 "받음". 보낸 돈은 "보냄"을 고르세요 (그 사람의 경조사로 등록돼요)'],
    ['· 행사: 비우면 행사 종류로 이름을 붙여요 (예: 내 결혼식). 같은 날짜·같은 행사 이름은 한 행사로 묶여요'],
    ['· 행사 종류: 목록에 없으면 직접 쓰세요 (예: 칠순, 집들이)'],
    ['· 관계·소속·방식·참석·감사 인사·메모: 비워도 돼요. 소속은 이름이 같은 사람을 구분할 때 써요'],
    [''],
    ['예시 (이 시트의 예시는 등록되지 않아요)', { bold: true }],
  ]
  for (const [text, font] of lines) {
    const row = guide.addRow([text])
    if (font) row.font = font
  }
  const exHead = guide.addRow([...RECORD_COLUMNS])
  exHead.font = { bold: true }
  exHead.fill = HEADER_FILL
  guide.addRow(['2024-05-18', '내 결혼식', '결혼', '홍길동', '친구', '대학 동기', '받음', 100000, '현금', '참석', '완료', ''])
  guide.addRow(['2024-05-18', '내 결혼식', '결혼', '김철수', '직장', '○○회사', '받음', 50000, '계좌이체', '', '', ''])
  guide.addRow(['2026-09-14', '이영희 부친상', '장례', '이영희', '친구', '', '보냄', 50000, '계좌이체', '참석', '', ''])
  RECORD_COLUMNS.forEach((_, i) => i > 0 && (guide.getColumn(i + 1).width = 11))

  return new Uint8Array(await wb.xlsx.writeBuffer())
}
