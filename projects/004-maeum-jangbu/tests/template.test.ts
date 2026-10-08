import { describe, expect, it } from 'vitest'
import ExcelJS from 'exceljs'
import { buildTemplate, readWorkbook, TEMPLATE_ROWS } from '../src/lib/excel'
import { RECORD_COLUMNS, parseCsv, templateCsv } from '../src/lib/sheet'
import { mapHeader, tableToData } from '../src/lib/importData'

const toArrayBuffer = (u: Uint8Array) => u.buffer.slice(u.byteOffset, u.byteOffset + u.byteLength) as ArrayBuffer

describe('일괄 등록 양식', () => {
  it('엑셀 양식: 전체 내역(필수 표시·드롭다운) + 작성 방법 시트', async () => {
    const wb = new ExcelJS.Workbook()
    await wb.xlsx.load(toArrayBuffer(await buildTemplate()))
    expect(wb.worksheets.map((w) => w.name)).toEqual(['전체 내역', '작성 방법'])
    const ws = wb.getWorksheet('전체 내역')!
    expect(ws.getRow(1).getCell(1).value).toBe('날짜 *')
    expect(ws.getRow(1).getCell(4).value).toBe('이름 *')
    expect(ws.getRow(1).getCell(8).value).toBe('금액 *')
    // 받음/보냄(7열) 드롭다운, 행사 종류(3열)는 목록 밖 허용
    expect(ws.getCell(2, 7).dataValidation).toMatchObject({ type: 'list', formulae: ['"받음,보냄"'] })
    expect(ws.getCell(TEMPLATE_ROWS + 1, 7).dataValidation?.type).toBe('list')
    expect(ws.getCell(2, 3).dataValidation?.showErrorMessage).toBeFalsy()
    expect(ws.getCell(2, 7).dataValidation?.showErrorMessage).toBe(true)
  })

  it('빈 양식을 그대로 올리면 머리글만 있고, 머리글은 모두 알아본다 (필수 표시 * 무시)', async () => {
    const table = await readWorkbook(toArrayBuffer(await buildTemplate()))
    expect(table).toHaveLength(1)
    const { fields, unknown } = mapHeader(table[0])
    expect(fields.every((f) => f !== null)).toBe(true)
    expect(unknown).toEqual([])
  })

  it('양식에 적은 줄만 등록되고, 작성 방법 시트의 예시는 등록되지 않는다', async () => {
    const wb = new ExcelJS.Workbook()
    await wb.xlsx.load(toArrayBuffer(await buildTemplate()))
    const ws = wb.getWorksheet('전체 내역')!
    // 엑셀에서 날짜 칸에 2024-05-18을 치면 날짜 값(UTC 자정)으로 저장된다
    ws.getRow(2).values = [new Date(Date.UTC(2024, 4, 18)), '내 결혼식', '결혼', '가나다', '친구', '', '받음', 100000, '현금', '참석', '완료', '']
    ws.getRow(3).values = [new Date(Date.UTC(2024, 4, 18)), '내 결혼식', '결혼', '라마바', '직장', 'A사', '', '5만', '계좌이체']
    ws.getRow(4).values = ['2026.09.14', '사아자 부친상', '', '사아자', '', '', '보냄', '50,000원']
    const filled = new Uint8Array(await wb.xlsx.writeBuffer())

    const { data, issues } = tableToData(await readWorkbook(toArrayBuffer(filled)))
    expect(issues).toEqual([])
    expect(data.records.map((r) => [r.direction, r.amount, r.method, r.thanked])).toEqual([
      ['received', 100000, 'cash', true],
      ['received', 50000, 'transfer', false],
      ['given', 50000, 'cash', false],
    ])
    expect(data.events.map((e) => [e.owner, e.title, e.type, e.date])).toEqual([
      ['mine', '내 결혼식', 'wedding', '2024-05-18'],
      ['theirs', '사아자 부친상', 'funeral', '2026-09-14'],
    ])
    expect(data.people.map((p) => p.name)).toEqual(['가나다', '라마바', '사아자'])
  })

  it('CSV 양식: BOM + 머리글만', () => {
    const csv = templateCsv()
    expect(csv.startsWith('﻿')).toBe(true)
    expect(parseCsv(csv)).toEqual([[...RECORD_COLUMNS]])
  })
})
