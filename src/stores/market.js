import { computed, reactive } from 'vue'
import { api } from '../services/api'
import {
  apiCallLogs,
  batches,
  collectConfigs as seedCollectConfigs,
  collectRegions as seedCollectRegions,
  demoQuotes,
  logs,
  mappings,
  marketStats,
  materials,
  pricingRuleGroups,
  quotes as seedQuotes,
  results,
  schedules,
  sources,
  sourceSync as seedSourceSync,
  syncStatus,
  templates
} from '../data/seed'

const DAY_MS = 86400000
const toTime = (iso) => Date.parse(`${iso}T00:00:00Z`)

function rollingAverages(rows) {
  return rows.map((quote) => {
    const end = toTime(quote.date)
    const start = end - 6 * DAY_MS
    const values = rows
      .filter((item) => {
        const time = toTime(item.date)
        return time >= start && time <= end
      })
      .map((item) => item.avg)
    return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
  })
}

const seedRolling = rollingAverages(seedQuotes)

const initialQuotes = [
  ...seedQuotes.map((quote, index) => ({
    id: `seed-${index}`,
    materialCode: 'WB00001',
    materialName: '清远机生铝',
    category: '废金属',
    source: '富宝资讯',
    externalName: '清远机械生铝',
    systemName: '清远机生铝（WB00001）',
    date: quote.date,
    avg: quote.avg,
    range: quote.range,
    change: quote.change,
    periodAvg: seedRolling[index],
    capturedAt: syncStatus.lastSync.slice(11),
    status: '成功',
    matchStatus: 'matched',
    isDemo: false
  })),
  ...demoQuotes.map((row, index) => ({
    id: `demo-${index}`,
    materialCode: row.materialCode,
    materialName: row.materialCode ? row.systemName.split('（')[0] : '',
    category: row.category,
    source: row.source,
    externalName: row.externalName,
    systemName: row.systemName,
    date: row.date,
    avg: row.avg ?? null,
    range: row.rawPrice,
    change: row.change ?? '—',
    periodAvg: row.periodAvg,
    capturedAt: row.capturedAt,
    status: row.status,
    matchStatus: row.status === '未匹配' ? 'unmatched' : 'matched',
    isDemo: true
  }))
]

const PAGE_SIZE_KEY = 'market.ledgerPageSize'
const PAGE_SIZES = [10, 20, 50, 100]

function readPageSize() {
  try {
    const value = Number(window.localStorage.getItem(PAGE_SIZE_KEY))
    if (PAGE_SIZES.includes(value)) return value
  } catch {
    // 忽略隐私模式等 localStorage 不可用场景
  }
  return 10
}

const state = reactive({
  sources,
  materials,
  mappings,
  templates,
  params: [],
  pricingRules: { groups: pricingRuleGroups, items: [] },
  schedules,
  batches,
  results,
  logs,
  apiCallLogs,
  syncStatus,
  marketStats,
  quotes: initialQuotes,
  collectConfigs: seedCollectConfigs,
  collectToken: {
    present: false,
    valid: false,
    masked: '',
    expiry: '',
    remainingHours: null,
    source: 'missing',
    filePath: 'auth_token.txt',
    autoRenew: false,
    autoRenewAccount: '',
    refreshError: '',
    loading: false,
    warning: ''
  },
  regions: seedCollectRegions,
  sourceSync: seedSourceSync,
  dataSource: 'seed',
  apiOnline: false,
  loading: false,
  loaded: false,
  syncing: false,
  error: '',
  dashboardMaterial: 'WB00001',
  dashboardRange: 30,
  ledger: {
    items: [],
    page: 1,
    pageSize: readPageSize(),
    total: 0,
    totalPages: 1,
    loading: false,
    error: ''
  },
  toast: { visible: false, message: '' }
})

let toastTimer = null

function notify(message) {
  state.toast.message = message
  state.toast.visible = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    state.toast.visible = false
  }, 2600)
}

function nowText() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Math.round(Number(value)).toLocaleString('en-US')
}

function formatSigned(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  if (number === 0) return '0'
  return `${number > 0 ? '+' : ''}${number.toLocaleString('en-US')}`
}

function formatPrice2(value) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (Number.isNaN(number)) return '—'
  return number.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

function formatAdjust(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  if (number === 0) return '0（不增不减）'
  return `${number > 0 ? '+' : ''}${number.toLocaleString('en-US')}`
}

// 上一完整周（周一至周日）；只有周一至周五的报价参与均价
function completeWeekRange(reference = new Date()) {
  const day = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate())
  const weekday = day.getDay() || 7
  const sunday = new Date(day.getTime() - weekday * DAY_MS)
  const monday = new Date(sunday.getTime() - 6 * DAY_MS)
  return { start: toIso(monday), end: toIso(sunday) }
}

function toIso(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function weekdayOf(iso) {
  const day = new Date(`${iso}T00:00:00`).getDay()
  return day === 0 ? 7 : day
}

function weekAverageLocal(rows, reference = new Date()) {
  const range = completeWeekRange(reference)
  const values = rows
    .filter((item) => item.date >= range.start && item.date <= range.end)
    .filter((item) => weekdayOf(item.date) <= 5)
    .map((item) => Number(item.avg))
    .filter((value) => Number.isFinite(value))
  if (!values.length) {
    return { start: range.start, end: range.end, average: null, days: 0 }
  }
  const total = values.reduce((sum, value) => sum + value, 0)
  return {
    start: range.start,
    end: range.end,
    average: Math.round((total / values.length) * 100) / 100,
    days: values.length
  }
}

function calcPriceOf(periodAvg, offset, coefficient) {
  if (periodAvg === null || periodAvg === undefined || periodAvg === '') return null
  const base = Number(periodAvg) + Number(offset || 0)
  const coeff = coefficient === null || coefficient === undefined ? 1 : Number(coefficient)
  return Math.round(base * coeff * 100) / 100
}

function rulesForMaterial(code) {
  const group = state.pricingRules.groups.find((item) => item.sourceMaterialCode === code)
  return group ? group.rules : []
}

const primaryQuotes = computed(() =>
  state.quotes
    .filter((quote) => quote.materialCode === 'WB00001' && !quote.isDemo)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
)

function quotesForMaterial(code) {
  return state.quotes
    .filter((quote) => quote.materialCode === code && !quote.isDemo)
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
}

const dashboardMaterialQuotes = computed(() => quotesForMaterial(state.dashboardMaterial))

const latestQuote = computed(() => {
  const rows = dashboardMaterialQuotes.value
  return rows[rows.length - 1] || null
})

function localLedger(query) {
  const sourceName = state.sources.find((item) => item.code === query.source)?.name
  const keyword = (query.keyword || '').toLowerCase()
  const rows = state.quotes
    .filter((quote) => {
      if (query.source && quote.source !== (sourceName || query.source)) return false
      if (query.category && quote.category !== query.category) return false
      if (query.startDate && quote.date < query.startDate) return false
      if (query.endDate && quote.date > query.endDate) return false
      if (keyword) {
        const text = `${quote.materialCode} ${quote.materialName} ${quote.externalName} ${quote.systemName} ${quote.range}`.toLowerCase()
        if (!text.includes(keyword)) return false
      }
      return true
    })
    .slice()
    .sort((a, b) => b.date.localeCompare(a.date) || String(b.id).localeCompare(String(a.id)))

  const pageSize = query.pageSize
  const total = rows.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const page = Math.min(Math.max(Number(query.page) || 1, 1), totalPages)
  const start = (page - 1) * pageSize
  state.ledger = {
    items: rows.slice(start, start + pageSize),
    page,
    pageSize,
    total,
    totalPages,
    loading: false,
    error: ''
  }
}

async function loadLedger(params = {}) {
  const requestedSize = Number(params.pageSize)
  const pageSize = PAGE_SIZES.includes(requestedSize)
    ? requestedSize
    : state.ledger.pageSize
  const query = {
    page: Math.max(Number(params.page) || 1, 1),
    pageSize,
    source: params.source || '',
    category: params.category || '',
    startDate: params.startDate || '',
    endDate: params.endDate || '',
    keyword: params.keyword || ''
  }
  state.ledger.pageSize = pageSize
  state.ledger.loading = true
  try {
    window.localStorage.setItem(PAGE_SIZE_KEY, String(pageSize))
  } catch {
    // 忽略 localStorage 不可用
  }
  try {
    const data = await api.quotes(query)
    state.ledger = {
      items: data.items,
      page: data.page,
      pageSize: data.pageSize,
      total: data.total,
      totalPages: data.totalPages,
      loading: false,
      error: ''
    }
    state.apiOnline = true
    state.dataSource = 'api'
    state.error = ''
  } catch (error) {
    localLedger(query)
    state.apiOnline = false
    state.dataSource = 'seed'
    state.error = error.message
  }
  return state.ledger
}

const DASHBOARD_SOURCES = {
  WB00001: {
    name: '富宝资讯',
    material: '清远机械生铝',
    diid: '163321',
    spec: '机生铝 Fe6%-8%',
    tax: '不含税',
    unit: '元/吨'
  },
  WB00002: {
    name: '富宝资讯',
    material: '佛山黄杂铜',
    diid: '32105',
    spec: '黄杂铜',
    tax: '不含税',
    unit: '元/吨'
  }
}

function dashboardSourceFor(code) {
  const config = state.collectConfigs.find(
    (item) => item.materialCode === code && item.status !== '已删除'
  )
  if (!config) return DASHBOARD_SOURCES[code] || state.syncStatus.source
  return {
    name: config.source,
    material: config.externalName,
    diid: config.productId,
    spec: config.spec || config.webName,
    tax: config.tax,
    unit: config.unit || '元/吨'
  }
}

const dashboardMaterials = computed(() => {
  const options = []
  const seen = new Set()
  state.collectConfigs.forEach((item) => {
    if (!item.materialCode || seen.has(item.materialCode)) return
    if (item.status === '已删除' || item.status === '停用') return
    if (item.sourceEnabled === false) return
    seen.add(item.materialCode)
    options.push({
      code: item.materialCode,
      name: item.materialName || item.externalName
    })
  })
  if (options.length) return options
  return state.materials.map((item) => ({ code: item.code, name: item.name }))
})

const dashboard = computed(() => {
  const code = state.dashboardMaterial
  const range = Number(state.dashboardRange)
  const material = state.materials.find((item) => item.code === code) || state.materials[0]
  const rows = quotesForMaterial(code)
  const hasData = rows.length > 0
  const source = dashboardSourceFor(code)
  const coverage = hasData
    ? {
        start: rows[0].date,
        end: rows[rows.length - 1].date,
        days: new Set(rows.map((quote) => quote.date)).size
      }
    : { start: '', end: '', days: 0 }
  const base = { code, material, hasData, range, source, coverage }

  if (!hasData) {
    return { ...base, series: [], rangeLabel: '—', stats: null }
  }

  const latest = rows[rows.length - 1]
  const series = rows.slice(-range)
  const week = weekAverageLocal(rows)
  const weekAvg = week.average
  const previousWeek = weekAverageLocal(rows, new Date(`${week.start}T00:00:00`))
  const prevAvg = previousWeek.average
  const high = rows.reduce((best, quote) => (quote.avg > best.avg ? quote : best), rows[0])
  const low = rows.reduce((best, quote) => (quote.avg < best.avg ? quote : best), rows[0])
  const rules = rulesForMaterial(code).filter((rule) => rule.status === '生效')
  const primaryRule = rules[0] || null
  const calcPrice = primaryRule
    ? calcPriceOf(weekAvg, primaryRule.offset, primaryRule.coefficient)
    : null
  const changePct = prevAvg && weekAvg ? ((weekAvg - prevAvg) / prevAvg) * 100 : null

  return {
    ...base,
    series,
    rangeLabel: `近${range}个交易日 · ${series[0].date} ~ ${latest.date}`,
    week,
    stats: {
      weekAvg,
      prevAvg,
      changePct,
      calcPrice,
      offset: primaryRule ? primaryRule.offset : null,
      coefficient: primaryRule ? primaryRule.coefficient : null,
      ruleCount: rules.length,
      systemMaterials: rules.map((rule) => `${rule.materialCode} ${rule.materialName}`),
      high,
      low
    }
  }
})

function localLog(type, content, operator = '王莉洁') {
  const entry = {
    time: nowText(),
    type,
    operator,
    content,
    ip: '10.0.1.xx'
  }
  state.logs.unshift(entry)
  return entry
}

function addLogEntry(log) {
  if (log) state.logs.unshift(log)
}

function replaceItem(listName, item) {
  const list = state[listName]
  const index = list.findIndex((entry) => entry.id === item.id)
  if (index >= 0) {
    list[index] = item
  } else {
    list.unshift(item)
  }
}

function replaceSourceSync(item) {
  if (!item) return
  const index = state.sourceSync.findIndex((entry) => entry.id === item.id)
  if (index >= 0) {
    state.sourceSync[index] = item
  } else {
    state.sourceSync.push(item)
  }
}

async function refreshSourceSync() {
  if (!state.apiOnline) return
  try {
    const data = await api.collectOverview()
    state.sourceSync = data.sources || state.sourceSync
  } catch {
    // 汇总刷新失败不阻断主操作
  }
}

async function loadAll() {
  state.loading = true
  try {
    const data = await api.bootstrap()
    state.sources = data.sources
    state.materials = data.materials
    state.mappings = data.mappings
    state.templates = data.templates
    state.params = data.params || []
    if (data.pricingRules) {
      state.pricingRules = {
        groups: data.pricingRules.groups || [],
        items: data.pricingRules.items || []
      }
    }
    state.schedules = data.schedules
    state.batches = data.batches
    state.results = data.results
    state.logs = data.logs
    state.apiCallLogs = data.apiCallLogs
    state.syncStatus = data.syncStatus
    state.syncing = Boolean(data.syncStatus && data.syncStatus.collectRunning)
    if (state.syncing) pollCollectResult()
    state.marketStats = data.marketStats
    state.collectConfigs = data.collectConfigs || state.collectConfigs
    state.sourceSync = data.sourceSync || state.sourceSync
    await loadCollectToken()
    state.quotes = data.quotes
    state.dataSource = 'api'
    const codes = state.collectConfigs
      .filter((item) => item.materialCode && item.status !== '已删除')
      .map((item) => item.materialCode)
    if (codes.length && !codes.includes(state.dashboardMaterial)) {
      state.dashboardMaterial = codes[0]
    }
    state.apiOnline = true
    state.error = ''
  } catch (error) {
    state.apiOnline = false
    state.dataSource = 'seed'
    state.error = error.message
    notify('后端未连接，当前使用本地演示数据')
  } finally {
    state.loading = false
    state.loaded = true
  }
}

async function toggleMapping(id) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.toggleMapping(id)
      replaceItem('mappings', item)
      addLogEntry(log)
      await loadAll()
      notify(`映射已${item.status === '生效' ? '启用' : '停用'}（计价${item.status === '生效' ? '恢复' : '停止'}，采集不受影响）`)
      return
    } catch (error) {
      notify(`保存失败：${error.message}`)
      return
    }
  }

  const mapping = state.mappings.find((item) => item.id === id)
  if (!mapping) return
  mapping.status = mapping.status === '生效' ? '停用' : '生效'
  localLog(
    '物料映射变更',
    `${mapping.status}：${mapping.materialCode} ${mapping.materialName} ↔ ${mapping.source}「${mapping.keyword}」`
  )
  notify(`映射已${mapping.status === '生效' ? '启用' : '停用'}（本地演示）`)
}

async function updateParam(id, payload) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.updateParam(id, payload)
      replaceItem('params', item)
      addLogEntry(log)
      notify('定价参数已保存')
      return true
    } catch (error) {
      notify(`保存失败：${error.message}`)
      return false
    }
  }

  const param = state.params.find((item) => item.id === id)
  if (!param) return false
  Object.assign(param, payload)
  localLog(
    '参数修改',
    `${param.materialCode} 定价参数已保存：偏移 ${formatSigned(param.offset)} / 系数 ${Number(param.coefficient).toFixed(2)}`
  )
  notify('定价参数已保存（本地演示）')
  return true
}

async function updateTemplate(id, payload) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.updateTemplate(id, payload)
      replaceItem('templates', item)
      addLogEntry(log)
      notify(`${item.code} 模板已保存`)
      return true
    } catch (error) {
      notify(`保存失败：${error.message}`)
      return false
    }
  }

  const template = state.templates.find((item) => item.id === id)
  if (!template) return false
  Object.assign(template, payload)
  localLog('模板修改', `${template.code} 模板已保存：${payload.factors.join('、')}`)
  notify(`${template.code} 模板已保存（本地演示）`)
  return true
}

async function reviewResult(id, status) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.reviewResult(id, status)
      replaceItem('results', item)
      addLogEntry(log)
      notify(`已将 ${item.materialCode} 标记为${status}`)
      return
    } catch (error) {
      notify(`复核失败：${error.message}`)
      return
    }
  }

  const result = state.results.find((item) => item.id === id)
  if (!result) return
  result.reviewStatus = status
  localLog('复核', `${result.materialCode} ${result.materialName} 计价结果：${status}`)
  notify(`已将 ${result.materialCode} 标记为${status}（本地演示）`)
}

async function batchApprove() {
  if (state.apiOnline) {
    try {
      const data = await api.batchApprove()
      data.items.forEach((item) => replaceItem('results', item))
      addLogEntry(data.log)
      notify(data.count ? `已批量复核通过 ${data.count} 条` : '当前没有待复核结果')
      return
    } catch (error) {
      notify(`批量复核失败：${error.message}`)
      return
    }
  }

  const pending = state.results.filter((item) => item.reviewStatus === '待复核')
  pending.forEach((item) => {
    item.reviewStatus = '已复核'
  })
  if (pending.length) {
    localLog('复核', `批量复核通过 ${pending.length} 条计价结果`)
    notify(`已批量复核通过 ${pending.length} 条（本地演示）`)
  } else {
    notify('当前没有待复核结果')
  }
}

async function runSchedule(id) {
  if (state.apiOnline) {
    try {
      const data = await api.runSchedule(id)
      replaceItem('schedules', data.item)
      if (data.run) replaceItem('batches', data.run)
      if (data.results) {
        data.results.forEach((item) => replaceItem('results', item))
      }
      addLogEntry(data.log)
      const count = data.results ? data.results.length : 0
      notify(count ? `已生成 ${count} 条计价结果` : '任务已执行')
      return data
    } catch (error) {
      notify(`执行失败：${error.message}`)
      return null
    }
  }

  const schedule = state.schedules.find((item) => item.id === id)
  if (!schedule) return null
  schedule.lastRun = nowText().slice(0, 16)
  localLog('计价执行', `${schedule.name} 手动触发完成`)
  notify(`${schedule.name} 已触发（本地演示）`)
  return { item: schedule, results: [] }
}

async function loadRegions(refresh = false) {
  if (!state.apiOnline) {
    state.regions = seedCollectRegions
    return state.regions
  }
  try {
    const data = await api.collectRegions(refresh)
    state.regions = data
    if (data.warning) notify(data.warning)
    return data
  } catch (error) {
    notify(`省市加载失败：${error.message}`)
    return state.regions
  }
}

async function searchCollect(payload) {
  if (!state.apiOnline) throw new Error('后端未连接，无法搜索富宝')
  return api.searchCollect(payload)
}

async function saveCollect(id, payload) {
  if (!state.apiOnline) throw new Error('后端未连接，无法保存采集配置')
  const data = id ? await api.updateCollect(id, payload) : await api.createCollect(payload)
  replaceItem('collectConfigs', data.item)
  addLogEntry(data.log)
  await refreshSourceSync()
  const backfill = data.backfill || null
  if (backfill && backfill.started) {
    notify(`采集配置已${data.created ? '新增' : '保存'}，正在同步近 ${backfill.days} 天历史数据（${backfill.windows} 个窗口）`)
  } else if (backfill && backfill.reason) {
    notify(`采集配置已保存；历史同步未启动：${backfill.reason}`)
  } else {
    notify(data.created ? '采集配置已新增' : '采集配置已保存')
  }
  return data
}

async function refreshCollectConfigs() {
  if (!state.apiOnline) return state.collectConfigs
  try {
    const data = await api.collectConfigs()
    state.collectConfigs = data.items || []
    await refreshSourceSync()
  } catch {
    // 轮询失败不打断页面
  }
  return state.collectConfigs
}

async function loadCollectToken() {
  if (!state.apiOnline) return state.collectToken
  state.collectToken = { ...state.collectToken, loading: true }
  try {
    const data = await api.collectTokenStatus()
    state.collectToken = { ...state.collectToken, ...data, loading: false }
  } catch {
    state.collectToken = { ...state.collectToken, loading: false }
  }
  return state.collectToken
}

async function saveCollectToken(token) {
  if (!state.apiOnline) throw new Error('后端未连接，无法保存 token')
  const data = await api.saveCollectToken(token)
  state.collectToken = { ...state.collectToken, ...data, loading: false }
  if (data.log) addLogEntry(data.log)
  notify(data.warning || '富宝 token 已保存')
  return data
}

async function refreshCollectToken() {
  if (!state.apiOnline) throw new Error('后端未连接，无法自动续期')
  const data = await api.refreshCollectToken()
  state.collectToken = { ...state.collectToken, ...(data.token || {}), loading: false }
  if (data.log) addLogEntry(data.log)
  notify(data.message || 'token 已自动续期')
  return data
}

async function saveCollectCredentials(username, password) {
  if (!state.apiOnline) throw new Error('后端未连接，无法保存自动续期账号')
  const data = await api.saveCollectCredentials(username, password)
  state.collectToken = {
    ...state.collectToken,
    ...(data.token || {}),
    autoRenew: true,
    autoRenewAccount: data.credentials?.username || '',
    refreshError: '',
    loading: false
  }
  if (data.log) addLogEntry(data.log)
  notify(data.message || '账号登录成功，自动续期已启用')
  return data
}

async function deleteCollectCredentials() {
  if (!state.apiOnline) throw new Error('后端未连接，无法关闭自动续期')
  const data = await api.deleteCollectCredentials()
  state.collectToken = {
    ...state.collectToken,
    autoRenew: false,
    autoRenewAccount: '',
    refreshError: '',
    loading: false
  }
  if (data.log) addLogEntry(data.log)
  notify(data.message || '账号已退出，自动续期已关闭')
  return data
}

async function toggleSource(id) {
  if (!state.apiOnline) throw new Error('后端未连接，无法切换网站同步')
  const { item, log } = await api.toggleSource(id)
  replaceSourceSync(item)
  state.collectConfigs.forEach((config) => {
    if (config.sourceCode === item.code) config.sourceEnabled = item.enabled
  })
  addLogEntry(log)
  notify(`「${item.name}」网站同步已${item.enabled ? '启用' : '停用'}`)
  return item
}

async function batchToggle(sourceId, enabled) {
  if (!state.apiOnline) throw new Error('后端未连接，无法批量切换')
  const data = await api.batchToggleCollect(sourceId, enabled)
  await loadAll()
  notify(`已将「${data.item.name}」下 ${data.updated} 条物料${enabled ? '启用' : '停用'}`)
  return data
}

async function saveMapping(id, payload) {
  if (!state.apiOnline) {
    notify('后端未连接，无法保存映射')
    return null
  }
  try {
    const data = id
      ? await api.updateMapping(id, payload)
      : await api.createMapping(payload)
    replaceItem('mappings', data.item)
    addLogEntry(data.log)
    // 映射即计价规则，同步刷新计价规则页数据
    await loadPricingRules()
    notify(id ? '映射已保存' : '映射已新增')
    return data.item
  } catch (error) {
    notify(`保存失败：${error.message}`)
    return null
  }
}

async function importMappings(text) {
  if (!state.apiOnline) {
    notify('后端未连接，无法批量导入')
    return null
  }
  try {
    const data = await api.importMappings(text)
    await loadAll()
    notify(`批量导入完成：新增 ${data.created}，更新 ${data.updated}，失败 ${data.errors.length}`)
    return data
  } catch (error) {
    notify(`导入失败：${error.message}`)
    return null
  }
}

async function createParam(payload) {
  if (!state.apiOnline) {
    notify('后端未连接，无法新增物料配置')
    return null
  }
  try {
    const data = await api.createParam(payload)
    await loadAll()
    notify(`${data.item.materialCode} 定价参数 v${data.item.version} 已新增`)
    return data.item
  } catch (error) {
    notify(`新增失败：${error.message}`)
    return null
  }
}

// ---------------------------------------------------------------- 物料计价规则
function findRule(id) {
  for (const group of state.pricingRules.groups) {
    const rule = group.rules.find((item) => item.id === id)
    if (rule) return { group, rule }
  }
  return { group: null, rule: null }
}

function refreshRulePreview(group, rule) {
  rule.previewPrice = calcPriceOf(group.periodAvg, rule.offset, rule.coefficient)
}

async function loadPricingRules() {
  if (!state.apiOnline) return state.pricingRules
  try {
    state.pricingRules = await api.pricingRules()
  } catch (error) {
    notify(`计价规则加载失败：${error.message}`)
  }
  return state.pricingRules
}

async function updatePricingRule(id, payload) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.updatePricingRule(id, payload)
      const { group } = findRule(id)
      if (group) {
        const index = group.rules.findIndex((rule) => rule.id === id)
        if (index >= 0) group.rules[index] = item
      }
      addLogEntry(log)
      notify(`已保存 ${item.materialCode} ${item.materialName} 计价规则`)
      return true
    } catch (error) {
      notify(`保存失败：${error.message}`)
      return false
    }
  }

  const { group, rule } = findRule(id)
  if (!rule) return false
  Object.assign(rule, payload)
  refreshRulePreview(group, rule)
  localLog(
    '参数修改',
    `${group.sourceMaterialCode} → ${rule.materialCode} 计价规则：固定调整值 ${formatSigned(rule.offset)} / 调价系数 ${Number(rule.coefficient || 1).toFixed(2)}`
  )
  notify('计价规则已保存（本地演示）')
  return true
}

async function createPricingRule(payload) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.createPricingRule(payload)
      const group = state.pricingRules.groups.find(
        (entry) => entry.sourceConfigId === item.sourceConfigId
      )
      if (group) group.rules.push(item)
      addLogEntry(log)
      notify(`已新增 ${item.materialCode} ${item.materialName} 计价规则`)
      return item
    } catch (error) {
      notify(`新增失败：${error.message}`)
      return null
    }
  }

  const group = state.pricingRules.groups.find(
    (entry) => entry.sourceConfigId === Number(payload.sourceConfigId)
  )
  const material = state.materials.find((item) => item.code === payload.materialCode)
  if (!group || !material) return null
  const rule = {
    id: Date.now(),
    sourceConfigId: group.sourceConfigId,
    materialCode: material.code,
    materialName: material.name,
    materialType: material.materialType,
    templateCode: payload.templateCode || 'TPL02',
    period: payload.period || '周',
    offset: Number(payload.offset || 0),
    coefficient: Number(payload.coefficient ?? 1),
    status: '生效'
  }
  refreshRulePreview(group, rule)
  group.rules.push(rule)
  localLog(
    '参数修改',
    `新增计价规则：${group.sourceMaterialCode} → ${rule.materialCode} ${rule.materialName}`
  )
  notify('计价规则已新增（本地演示）')
  return rule
}

async function createMaterial(payload) {
  if (state.apiOnline) {
    try {
      const data = await api.createMaterial(payload)
      if (data.created) {
        state.materials.push(data.item)
        addLogEntry(data.log)
        notify(`已新增${data.item.materialType}物料 ${data.item.code} ${data.item.name}`)
      }
      return data.item
    } catch (error) {
      notify(`新增物料失败：${error.message}`)
      return null
    }
  }

  const materialType = payload.materialType || '系统'
  const existing = state.materials.find(
    (item) => item.name === payload.name && item.materialType === materialType
  )
  if (existing) return existing
  const prefix = materialType === '系统' ? 'XT' : 'WB'
  const numbers = state.materials
    .filter((item) => item.code.startsWith(prefix))
    .map((item) => Number(item.code.slice(2)) || 0)
  const code = `${prefix}${String(Math.max(0, ...numbers) + 1).padStart(5, '0')}`
  const item = {
    code,
    name: payload.name,
    category: '废金属',
    unit: '元/吨',
    materialType
  }
  state.materials.push(item)
  localLog('参数修改', `新增${materialType}物料：${code} ${item.name}`)
  notify(`已新增${materialType}物料 ${code} ${item.name}（本地演示）`)
  return item
}

async function applyGroupCoefficient(sourceConfigId, coefficient) {
  const value = Number(coefficient)
  if (!Number.isFinite(value)) {
    notify('请输入有效的调价系数')
    return false
  }
  if (state.apiOnline) {
    try {
      const data = await api.applyGroupCoefficient(sourceConfigId, value)
      const group = state.pricingRules.groups.find(
        (entry) => entry.sourceConfigId === sourceConfigId
      )
      if (group) {
        group.rules = group.rules.map((rule) => {
          const updated = data.items.find((item) => item.id === rule.id)
          return updated || rule
        })
      }
      addLogEntry(data.log)
      notify(`已将 ${data.items.length} 个系统物料的调价系数统一设为 ${value.toFixed(2)}`)
      return true
    } catch (error) {
      notify(`设置失败：${error.message}`)
      return false
    }
  }

  const group = state.pricingRules.groups.find(
    (entry) => entry.sourceConfigId === sourceConfigId
  )
  if (!group) return false
  group.rules.forEach((rule) => {
    rule.coefficient = value
    refreshRulePreview(group, rule)
  })
  localLog('参数修改', `统一调价系数：${group.sourceMaterialCode} 下 ${group.rules.length} 条规则设为 ${value.toFixed(2)}`)
  notify('统一调价系数已保存（本地演示）')
  return true
}

let collectTimer = null
let collectStartedAt = 0

async function pollCollectResult() {
  collectStartedAt = Date.now()
  clearTimeout(collectTimer)
  const tick = async () => {
    let status = null
    try {
      status = await api.syncStatus()
    } catch {
      // 轮询失败不打断，继续等待下一轮
    }
    if (status) {
      state.syncStatus = { ...state.syncStatus, ...status }
      state.apiOnline = true
    }
    if (status && status.collectRunning) {
      if (Date.now() - collectStartedAt > 20 * 60 * 1000) {
        state.syncing = false
        notify('采集任务长时间未结束，请稍后刷新查看结果')
        await loadAll()
        return
      }
      collectTimer = setTimeout(tick, 4000)
      return
    }
    state.syncing = false
    await loadAll()
    const result = state.syncStatus.lastResult
    const summary = state.syncStatus.runSummary || {}
    if (result === 'success') {
      notify('行情采集完成')
    } else if (result === 'partial' || result === 'init_partial') {
      notify(`行情采集部分完成：失败 ${summary.failed || 0} 个、未执行 ${summary.skipped || 0} 个`)
    } else if (result === 'failed' || result === 'error') {
      notify(`行情采集未完成：${state.syncStatus.lastError || '请查看同步详情'}`)
    } else {
      notify('采集任务已结束')
    }
  }
  collectTimer = setTimeout(tick, 3000)
}

async function runCollectNow() {
  if (!state.apiOnline) {
    notify('后端未连接，无法手动采集')
    return null
  }
  if (state.syncing) {
    notify('采集任务正在运行，请稍后')
    return null
  }
  const quota = state.syncStatus || {}
  if (quota.callsRemaining !== undefined && Number(quota.callsRemaining) <= 0) {
    notify(`今日接口配额已用完（${quota.callsToday || 0}/${quota.dailyCap || 0}），请明天再试`)
    return null
  }
  try {
    const data = await api.runCollect()
    addLogEntry(data.log)
    if (data.quota) {
      state.syncStatus = {
        ...state.syncStatus,
        dailyCap: data.quota.dailyCap,
        callsToday: data.quota.callsToday,
        callsRemaining: data.quota.callsRemaining
      }
    }
    state.syncing = true
    notify(data.message)
    pollCollectResult()
    return data
  } catch (error) {
    notify(`采集启动失败：${error.message}`)
    return null
  }
}

async function toggleCollect(id) {
  if (state.apiOnline) {
    try {
      const { item, log } = await api.toggleCollect(id)
      replaceItem('collectConfigs', item)
      addLogEntry(log)
      await refreshSourceSync()
      notify(`采集配置已${item.status}`)
      return
    } catch (error) {
      notify(`操作失败：${error.message}`)
      return
    }
  }
  const config = state.collectConfigs.find((item) => item.id === id)
  if (!config) return
  config.status = config.status === '启用' ? '停用' : '启用'
  localLog('采集配置', `${config.externalName}：${config.status}`)
  notify(`采集配置已${config.status}（本地演示）`)
}

async function verifyCollect(id) {
  if (!state.apiOnline) {
    notify('后端未连接，无法校验富宝产品')
    return
  }
  try {
    const { item, log } = await api.verifyCollect(id)
    replaceItem('collectConfigs', item)
    addLogEntry(log)
    await refreshSourceSync()
    notify('富宝产品校验通过')
  } catch (error) {
    notify(`校验失败：${error.message}`)
  }
}

async function backfillCollect(id, payload) {
  if (!state.apiOnline) {
    notify('后端未连接，无法启动历史回补')
    return
  }
  try {
    const data = await api.backfillCollect(id, payload)
    replaceItem('collectConfigs', data.item)
    addLogEntry(data.log)
    notify(data.message)
  } catch (error) {
    notify(`回补启动失败：${error.message}`)
  }
}

async function deleteCollect(id) {
  if (state.apiOnline) {
    try {
      const data = await api.deleteCollect(id)
      state.collectConfigs = state.collectConfigs.filter((item) => item.id !== id)
      addLogEntry(data.log)
      await refreshSourceSync()
      notify('采集配置已删除')
      return
    } catch (error) {
      notify(`删除失败：${error.message}`)
      return
    }
  }
  const config = state.collectConfigs.find((item) => item.id === id)
  state.collectConfigs = state.collectConfigs.filter((item) => item.id !== id)
  if (config) localLog('采集配置', `删除采集配置：${config.externalName}`)
  notify('采集配置已删除（本地演示）')
}

function addLog(type, content, operator = '王莉洁') {
  return localLog(type, content, operator)
}

const store = reactive({
  state,
  latestQuote,
  primaryQuotes,
  loadLedger,
  dashboard,
  dashboardMaterials,
  formatPrice,
  formatPrice2,
  formatSigned,
  formatAdjust,
  loadAll,
  loadRegions,
  toggleMapping,
  updateParam,
  updateTemplate,
  reviewResult,
  batchApprove,
  runSchedule,
  searchCollect,
  saveCollect,
  refreshCollectConfigs,
  loadCollectToken,
  saveCollectToken,
  refreshCollectToken,
  saveCollectCredentials,
  deleteCollectCredentials,
  saveMapping,
  importMappings,
  createParam,
  loadPricingRules,
  updatePricingRule,
  createPricingRule,
  createMaterial,
  applyGroupCoefficient,
  runCollectNow,
  toggleSource,
  batchToggle,
  toggleCollect,
  verifyCollect,
  backfillCollect,
  deleteCollect,
  notify,
  addLog
})

function useMarketStore() {
  return store
}

export { useMarketStore }
