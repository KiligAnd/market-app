let excelJsPromise = null

async function loadExcelJS() {
  if (!excelJsPromise) {
    excelJsPromise = import('exceljs').then((module) => module.default || module)
  }
  return excelJsPromise
}

const WEEKDAYS = 5

const pad = (value) => String(value).padStart(2, '0')

export function toIso(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function parseIso(text) {
  const value = String(text || '').slice(0, 10)
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function addDays(date, count) {
  const value = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  value.setDate(value.getDate() + count)
  return value
}

export function startOfWeek(date = new Date()) {
  const value = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const weekday = value.getDay() || 7
  return addDays(value, 1 - weekday)
}

export function endOfWeek(date = new Date()) {
  return addDays(startOfWeek(date), 6)
}

export function startOfMonth(date = new Date()) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function endOfMonth(date = new Date()) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0)
}

export function displayDate(date) {
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

export function displayMonthDay(date) {
  return `${date.getMonth() + 1}.${date.getDate()}`
}

export function displayRange(start, end) {
  return `${start.getFullYear()}.${start.getMonth() + 1}.${start.getDate()}-${end.getMonth() + 1}.${end.getDate()}`
}

export function displayRangeText(start, end) {
  return `${displayDate(start)}-${displayDate(end)}`
}

export function resolveReportRange(granularity, preset, customValue, now = new Date()) {
  if (granularity === 'month') {
    if (preset === 'lastMonth') {
      const start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      return { start, end: endOfMonth(start), granularity, preset }
    }
    if (preset === 'custom') {
      const value = String(customValue || '').slice(0, 7)
      const [year, month] = value.split('-').map(Number)
      if (year && month) {
        const start = new Date(year, month - 1, 1)
        return { start, end: endOfMonth(start), granularity, preset }
      }
    }
    const start = startOfMonth(now)
    return { start, end: endOfMonth(start), granularity, preset: 'thisMonth' }
  }

  if (preset === 'lastWeek') {
    const start = addDays(startOfWeek(now), -7)
    return { start, end: addDays(start, 6), granularity: 'week', preset }
  }
  if (preset === 'custom') {
    const picked = parseIso(customValue) || now
    const start = startOfWeek(picked)
    return { start, end: addDays(start, 6), granularity: 'week', preset }
  }
  const start = startOfWeek(now)
  return { start, end: addDays(start, 6), granularity: 'week', preset: 'thisWeek' }
}

export function executionWeekStart(result) {
  const periodEnd = parseIso(result.periodEnd)
  if (periodEnd) return addDays(periodEnd, 1)
  const periodStart = parseIso(result.periodStart)
  if (periodStart) return addDays(periodStart, 7)
  return null
}

function latestResults(results) {
  const seen = new Set()
  return [...(results || [])]
    .sort((a, b) => Number(b.id) - Number(a.id))
    .filter((row) => {
      const key = `${row.sourceMaterialCode}|${row.materialCode}|${row.periodStart}|${row.periodEnd}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

export function collectReportPeriods(results, range, granularity) {
  const groups = new Map()
  latestResults(results).forEach((row) => {
    const weekStart = executionWeekStart(row)
    if (!weekStart) return
    const weekEnd = addDays(weekStart, 6)
    if (granularity === 'week') {
      if (toIso(weekStart) !== toIso(range.start)) return
    } else if (weekStart < range.start || weekStart > range.end) {
      return
    }
    const key = toIso(weekStart)
    if (!groups.has(key)) {
      groups.set(key, { weekStart, weekEnd, rows: [] })
    }
    groups.get(key).rows.push(row)
  })
  return [...groups.values()]
    .sort((a, b) => a.weekStart - b.weekStart)
    .map((period) => ({
      ...period,
      rows: period.rows.sort((a, b) => {
        const sourceA = `${a.sourceMaterialCode || ''}${a.sourceMaterialName || ''}`
        const sourceB = `${b.sourceMaterialCode || ''}${b.sourceMaterialName || ''}`
        if (sourceA !== sourceB) return sourceA.localeCompare(sourceB, 'zh-CN')
        return String(a.materialCode || '').localeCompare(String(b.materialCode || ''), 'zh-CN')
      })
    }))
}

function weekdayDates(startText, endText) {
  let cursor = parseIso(startText)
  const end = parseIso(endText)
  if (!cursor) return []
  const dates = []
  const limit = end || addDays(cursor, 6)
  while (dates.length < WEEKDAYS && cursor <= limit) {
    const weekday = cursor.getDay() || 7
    if (weekday <= 5) dates.push(new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()))
    cursor = addDays(cursor, 1)
  }
  return dates
}

function quoteMap(quotes) {
  const map = new Map()
  ;(quotes || []).forEach((quote) => {
    if (!quote || quote.isDemo || !quote.materialCode || !quote.date) return
    const key = `${quote.materialCode}|${quote.date}`
    const current = map.get(key)
    if (!current || Number(quote.id) > Number(current.id)) map.set(key, quote)
  })
  return map
}

function numeric(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function round(value, digits = 0) {
  if (!Number.isFinite(value)) return null
  const base = 10 ** digits
  return Math.round(value * base) / base
}

function groupRows(rows) {
  const groups = []
  let current = null
  rows.forEach((row) => {
    const key = `${row.sourceMaterialCode || ''}|${row.sourceMaterialName || ''}|${row.source || ''}`
    if (!current || current.key !== key) {
      current = { key, rows: [] }
      groups.push(current)
    }
    current.rows.push(row)
  })
  return groups
}

const THIN = { style: 'thin', color: { argb: 'FF000000' } }
const THICK = { style: 'thick', color: { argb: 'FF000000' } }

function border(all = THIN) {
  return { top: all, left: all, right: all, bottom: all }
}

function applyBorder(cell, all = THIN) {
  cell.border = border(all)
}

function mergeGroup(worksheet, column, startRow, endRow) {
  if (endRow > startRow) {
    worksheet.mergeCells(`${column}${startRow}:${column}${endRow}`)
  }
}

function addWeeklySheet(workbook, period, quotes, materials, configs) {
  const sheetName = displayRange(period.weekStart, period.weekEnd).slice(0, 31)
  const ws = workbook.addWorksheet(sheetName, {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 2 }],
    pageSetup: { orientation: 'landscape', fitToPage: true, fitToWidth: 1, fitToHeight: 0 }
  })

  const title = `机动车资源室品种经销价格(${period.weekStart.getFullYear()}/${period.weekStart.getMonth() + 1}/${period.weekStart.getDate()}-${period.weekEnd.getFullYear()}/${period.weekEnd.getMonth() + 1}/${period.weekEnd.getDate()})`
  for (let column = 1; column <= 16; column += 1) {
    applyBorder(ws.getCell(1, column), THICK)
  }
  ws.mergeCells('A1:P1')
  ws.getCell('A1').value = title
  ws.getCell('A1').font = { name: '宋体', size: 12 }
  ws.getCell('A1').alignment = { horizontal: 'center', vertical: 'center' }
  ws.getRow(1).height = 21

  const dates = weekdayDates(period.rows[0]?.periodStart, period.rows[0]?.periodEnd)
  const dateLabels = dates.length
    ? dates.map((date) => displayMonthDay(date))
    : Array.from({ length: WEEKDAYS }, (_, index) => `取价日${index + 1}`)

  const headers = [
    '类别', '标的物', '序号', '品名', '单位',
    ...dateLabels,
    `${dateLabels[0]}-${dateLabels[dateLabels.length - 1]}\n网络平均价`,
    '固定系数',
    `${period.weekStart.getMonth() + 1}.${period.weekStart.getDate()}-${period.weekEnd.getMonth() + 1}.${period.weekEnd.getDate()}\n(含税)底标价`,
    '中标系数',
    `${period.weekStart.getMonth() + 1}.${period.weekStart.getDate()}-${period.weekEnd.getMonth() + 1}.${period.weekEnd.getDate()}（含税）执行价`,
    '浮动率来源'
  ]
  headers.forEach((value, index) => {
    const cell = ws.getCell(2, index + 1)
    cell.value = value
    cell.font = { name: '宋体', size: 8, bold: true }
    cell.alignment = { horizontal: 'center', vertical: 'center', wrapText: true }
    cell.border = border(THICK)
  })
  ws.getRow(2).height = 36

  const quoteIndex = quoteMap(quotes)
  const materialMap = new Map((materials || []).map((item) => [item.code, item]))
  const configMap = new Map((configs || []).map((item) => [item.materialCode, item]))
  const groups = groupRows(period.rows)
  let rowNumber = 3
  let sequence = 1

  groups.forEach((group, groupIndex) => {
    const startRow = rowNumber
    const endRow = rowNumber + group.rows.length - 1
    const first = group.rows[0]
    const sourceConfig = configMap.get(first.sourceMaterialCode)
    const sourceLabel = sourceConfig?.externalName
      || [sourceConfig?.source, sourceConfig?.place, sourceConfig?.webName,
          sourceConfig?.spec, sourceConfig?.tax].filter(Boolean).join('-')
      || first.sourceMaterialName
      || `${first.source || ''}${first.sourceMaterialCode || ''}`
    const dailyValues = dates.map((date) => {
      const quote = quoteIndex.get(`${first.sourceMaterialCode}|${toIso(date)}`)
      return quote ? numeric(quote.avg) : null
    })

    group.rows.forEach((row, index) => {
      const currentRow = startRow + index
      const material = materialMap.get(row.materialCode)
      const periodAvg = numeric(row.periodAvg)
      const offset = numeric(row.offset) ?? 0
      const coefficient = numeric(row.coefficient) ?? 1
      const basePrice = periodAvg !== null ? round(periodAvg + offset, 0) : null
      const execPrice = basePrice !== null ? round(basePrice * coefficient, 0) : null

      ws.getCell(currentRow, 1).value = first.sourceMaterialName || first.sourceMaterialCode || '网站物料'
      ws.getCell(currentRow, 2).value = `标的物${groupIndex + 1}`
      ws.getCell(currentRow, 3).value = sequence
      ws.getCell(currentRow, 4).value = row.materialName || row.materialCode || ''
      ws.getCell(currentRow, 5).value = material?.unit || '元/吨'
      if (index === 0) {
        dailyValues.forEach((value, dayIndex) => {
          ws.getCell(currentRow, 6 + dayIndex).value = value !== null ? value : '/'
        })
        const numericDays = dailyValues.filter((value) => value !== null)
        if (numericDays.length) {
          ws.getCell(currentRow, 11).value = {
            formula: `AVERAGE(F${currentRow}:J${currentRow})`,
            result: periodAvg !== null ? round(periodAvg, 2) : round(numericDays.reduce((sum, value) => sum + value, 0) / numericDays.length, 2)
          }
        } else {
          ws.getCell(currentRow, 11).value = periodAvg !== null ? periodAvg : '/'
        }
      }
      ws.getCell(currentRow, 12).value = offset
      if (basePrice !== null) {
        ws.getCell(currentRow, 13).value = {
          formula: `ROUND(K${startRow}+L${currentRow},0)`,
          result: basePrice
        }
      } else {
        ws.getCell(currentRow, 13).value = '/'
      }
      ws.getCell(currentRow, 14).value = coefficient
      if (execPrice !== null) {
        ws.getCell(currentRow, 15).value = {
          formula: `ROUND(M${currentRow}*N${currentRow},0)`,
          result: execPrice
        }
      } else {
        ws.getCell(currentRow, 15).value = '/'
      }
      ws.getCell(currentRow, 16).value = sourceLabel

      for (let column = 1; column <= 16; column += 1) {
        const cell = ws.getCell(currentRow, column)
        cell.font = { name: '等线', size: 8, bold: true }
        cell.alignment = {
          horizontal: column === 4 || column === 16 ? 'left' : 'center',
          vertical: 'center',
          wrapText: true
        }
        applyBorder(cell)
      }
      ws.getCell(currentRow, 3).numFmt = '0'
      for (let column = 6; column <= 11; column += 1) ws.getCell(currentRow, column).numFmt = '0'
      ws.getCell(currentRow, 12).numFmt = '0.##'
      ws.getCell(currentRow, 13).numFmt = '0'
      ws.getCell(currentRow, 14).numFmt = '0.00'
      ws.getCell(currentRow, 15).numFmt = '0'
      ws.getRow(currentRow).height = 18
      sequence += 1
    })

    mergeGroup(ws, 'A', startRow, endRow)
    mergeGroup(ws, 'B', startRow, endRow)
    for (let column = 6; column <= 10; column += 1) {
      const letter = String.fromCharCode(64 + column)
      mergeGroup(ws, letter, startRow, endRow)
    }
    mergeGroup(ws, 'K', startRow, endRow)
    mergeGroup(ws, 'P', startRow, endRow)
    rowNumber = endRow + 1
  })

  const lastRow = Math.max(rowNumber - 1, 2)
  for (let row = 1; row <= lastRow; row += 1) {
    for (let column = 1; column <= 16; column += 1) {
      const cell = ws.getCell(row, column)
      if (row === lastRow || column === 1 || column === 16) {
        cell.border = {
          ...cell.border,
          top: row === 1 ? THICK : cell.border?.top || THIN,
          left: column === 1 ? THICK : cell.border?.left || THIN,
          right: column === 16 ? THICK : cell.border?.right || THIN,
          bottom: row === lastRow ? THICK : cell.border?.bottom || THIN
        }
      }
    }
  }

  const widths = { A: 13, B: 8, C: 5, D: 20, E: 6, F: 7, G: 7, H: 7, I: 7, J: 7, K: 12, L: 8, M: 14, N: 12, O: 16, P: 36 }
  Object.entries(widths).forEach(([column, width]) => {
    ws.getColumn(column).width = width
  })

  return { rowCount: period.rows.length, title }
}

export async function buildPricingReportWorkbook({ periods, quotes, materials, configs }) {
  const ExcelJS = await loadExcelJS()
  const workbook = new ExcelJS.Workbook()
  workbook.creator = '商品行情计价系统'
  workbook.created = new Date()
  let rowCount = 0
  periods.forEach((period) => {
    const info = addWeeklySheet(workbook, period, quotes, materials, configs)
    rowCount += info.rowCount
  })
  return { workbook, rowCount }
}

export async function workbookBlob(workbook) {
  const buffer = await workbook.xlsx.writeBuffer()
  return new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
}
