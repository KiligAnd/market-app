import { quotes } from './quotes'

export { quotes }

export const sources = [
  { id: 'fubao', name: '富宝资讯' },
  { id: 'lingtong', name: '灵通平台' },
  { id: 'zhongfei', name: '中废网' }
]

export const materials = [
  { code: 'WB00001', name: '清远机生铝', category: '废金属', unit: '元/吨', materialType: '网站' },
  { code: 'WB00002', name: '佛山黄杂铜', category: '废金属', unit: '元/吨', materialType: '网站' },
  { code: 'XT00001', name: '铝', category: '废金属', unit: '元/吨', materialType: '系统' },
  { code: 'XT00002', name: '轻杂铝', category: '废金属', unit: '元/吨', materialType: '系统' },
  { code: 'XT00003', name: '铝质车底盘', category: '废金属', unit: '元/吨', materialType: '系统' },
  { code: 'XT00004', name: '废电线', category: '废金属', unit: '元/吨', materialType: '系统' },
  { code: 'XT00005', name: '混铝铜废电线', category: '废金属', unit: '元/吨', materialType: '系统' }
]

// 映射行 = 计价规则行：BIP系统物料 ↔ 网站爬虫物料对照（含计价参数）
export const mappings = [
  {
    id: 1,
    materialCode: 'XT00001',
    materialName: '铝',
    materialType: '系统',
    source: '富宝资讯',
    sourceCode: 'fubao',
    sourceConfigId: 1,
    configStatus: '启用',
    keyword: '机生铝',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    webName: '机生铝',
    place: '清远',
    spec: 'Fe6%-8%',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    productId: '636',
    provinceName: '广东省',
    cityName: '清远市',
    offset: 0,
    coefficient: 1.03,
    status: '生效',
    updatedAt: '2026-10-29 10:20:08'
  },
  {
    id: 2,
    materialCode: 'XT00002',
    materialName: '轻杂铝',
    materialType: '系统',
    source: '富宝资讯',
    sourceCode: 'fubao',
    sourceConfigId: 1,
    configStatus: '启用',
    keyword: '机生铝',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    webName: '机生铝',
    place: '清远',
    spec: 'Fe6%-8%',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    productId: '636',
    provinceName: '广东省',
    cityName: '清远市',
    offset: -842,
    coefficient: 1.03,
    status: '生效',
    updatedAt: '2026-10-29 10:20:08'
  },
  {
    id: 3,
    materialCode: 'XT00003',
    materialName: '铝质车底盘',
    materialType: '系统',
    source: '富宝资讯',
    sourceCode: 'fubao',
    sourceConfigId: 1,
    configStatus: '启用',
    keyword: '机生铝',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    webName: '机生铝',
    place: '清远',
    spec: 'Fe6%-8%',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    productId: '636',
    provinceName: '广东省',
    cityName: '清远市',
    offset: -4500,
    coefficient: 1.03,
    status: '生效',
    updatedAt: '2026-10-29 10:20:08'
  },
  {
    id: 4,
    materialCode: 'XT00004',
    materialName: '废电线',
    materialType: '系统',
    source: '富宝资讯',
    sourceCode: 'fubao',
    sourceConfigId: 2,
    configStatus: '启用',
    keyword: '黄杂铜',
    externalName: '佛山-黄杂铜-不含税',
    webName: '黄杂铜',
    place: '佛山',
    spec: '',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    productId: '1591',
    provinceName: '广东省',
    cityName: '佛山市',
    offset: -5800,
    coefficient: 1.18,
    status: '生效',
    updatedAt: '2026-10-29 10:20:08'
  },
  {
    id: 5,
    materialCode: 'XT00005',
    materialName: '混铝铜废电线',
    materialType: '系统',
    source: '富宝资讯',
    sourceCode: 'fubao',
    sourceConfigId: 2,
    configStatus: '启用',
    keyword: '黄杂铜',
    externalName: '佛山-黄杂铜-不含税',
    webName: '黄杂铜',
    place: '佛山',
    spec: '',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    productId: '1591',
    provinceName: '广东省',
    cityName: '佛山市',
    offset: -11802,
    coefficient: 1.18,
    status: '生效',
    updatedAt: '2026-10-29 10:20:08'
  }
]

export const templates = [
  {
    id: 1,
    code: 'TPL01',
    name: '固定价模板',
    formula: '直接使用人工录入售价',
    factors: ['固定售价'],
    enabled: true
  },
  {
    id: 2,
    code: 'TPL02',
    name: '周期均价+偏移系数模板',
    formula: '执行价 =（周期均价 ± 偏移）× 系数',
    factors: ['多源均价', '统计周期', '固定偏移', '调价系数'],
    enabled: true
  },
  {
    id: 3,
    code: 'TPL03',
    name: '跨期价差联动模板',
    formula: '本期价 = 本期均价 - 上期均价 + 上期售价',
    factors: ['多源均价', '统计周期', '上期价差', '上期售价联动'],
    enabled: true
  }
]

// 物料计价规则：一个网站物料可对应多个公司系统物料
// 计算售价 =（上一完整周均价 + 固定调整值）× 调价系数，保留两位小数
export const pricingRuleGroups = [
  {
    sourceConfigId: 1,
    sourceCode: 'fubao',
    source: '富宝资讯',
    productId: '636',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    region: '广东省清远市',
    status: '启用',
    sourceMaterialCode: 'WB00001',
    sourceMaterialName: '清远机生铝',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 17710,
    quoteDays: 5,
    rules: [
      {
        id: 1,
        sourceConfigId: 1,
        materialCode: 'XT00001',
        materialName: '铝',
        materialType: '系统',
        templateCode: 'TPL02',
        period: '周',
        offset: 0,
        coefficient: 1.03,
        status: '生效',
        previewPrice: 18241.3
      },
      {
        id: 2,
        sourceConfigId: 1,
        materialCode: 'XT00002',
        materialName: '轻杂铝',
        materialType: '系统',
        templateCode: 'TPL02',
        period: '周',
        offset: -842,
        coefficient: 1.03,
        status: '生效',
        previewPrice: 17374.04
      },
      {
        id: 3,
        sourceConfigId: 1,
        materialCode: 'XT00003',
        materialName: '铝质车底盘',
        materialType: '系统',
        templateCode: 'TPL02',
        period: '周',
        offset: -4500,
        coefficient: 1.03,
        status: '生效',
        previewPrice: 13606.3
      }
    ]
  },
  {
    sourceConfigId: 2,
    sourceCode: 'fubao',
    source: '富宝资讯',
    productId: '1591',
    externalName: '佛山-黄杂铜-不含税',
    region: '广东省佛山市',
    status: '启用',
    sourceMaterialCode: 'WB00002',
    sourceMaterialName: '佛山黄杂铜',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 57270,
    quoteDays: 5,
    rules: [
      {
        id: 4,
        sourceConfigId: 2,
        materialCode: 'XT00004',
        materialName: '废电线',
        materialType: '系统',
        templateCode: 'TPL02',
        period: '周',
        offset: -5800,
        coefficient: 1.18,
        status: '生效',
        previewPrice: 60734.6
      },
      {
        id: 5,
        sourceConfigId: 2,
        materialCode: 'XT00005',
        materialName: '混铝铜废电线',
        materialType: '系统',
        templateCode: 'TPL02',
        period: '周',
        offset: -11802,
        coefficient: 1.18,
        status: '生效',
        previewPrice: 53652.24
      }
    ]
  }
]

export const schedules = [
  {
    id: 1,
    name: '废金属周度计价',
    cycle: '每周一 08:00',
    status: '运行中',
    lastRun: '2026-10-27 08:00',
    nextRun: '2026-11-02 08:00'
  }
]

export const batches = [
  {
    id: 'BAT20261027',
    runAt: '2026-10-27 10:20:08',
    total: 1,
    success: 1,
    failed: 0,
    status: '成功'
  }
]

export const results = [
  {
    id: 1,
    batchId: 'BAT20261027',
    materialCode: 'XT00001',
    materialName: '铝',
    materialType: '系统',
    sourceMaterialCode: 'WB00001',
    sourceMaterialName: '清远机生铝',
    source: '富宝资讯',
    templateCode: 'TPL02',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 17710,
    offset: 0,
    coefficient: 1.03,
    calcPrice: 18241.3,
    syncStatus: '已同步',
    reviewStatus: '待复核',
    reviewer: '',
    reviewedAt: '',
    rejectReason: ''
  },
  {
    id: 2,
    batchId: 'BAT20261027',
    materialCode: 'XT00002',
    materialName: '轻杂铝',
    materialType: '系统',
    sourceMaterialCode: 'WB00001',
    sourceMaterialName: '清远机生铝',
    source: '富宝资讯',
    templateCode: 'TPL02',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 17710,
    offset: -842,
    coefficient: 1.03,
    calcPrice: 17374.04,
    syncStatus: '已同步',
    reviewStatus: '待复核',
    reviewer: '',
    reviewedAt: '',
    rejectReason: ''
  },
  {
    id: 3,
    batchId: 'BAT20261027',
    materialCode: 'XT00003',
    materialName: '铝质车底盘',
    materialType: '系统',
    sourceMaterialCode: 'WB00001',
    sourceMaterialName: '清远机生铝',
    source: '富宝资讯',
    templateCode: 'TPL02',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 17710,
    offset: -4500,
    coefficient: 1.03,
    calcPrice: 13606.3,
    syncStatus: '已同步',
    reviewStatus: '待复核',
    reviewer: '',
    reviewedAt: '',
    rejectReason: ''
  },
  {
    id: 4,
    batchId: 'BAT20261027',
    materialCode: 'XT00004',
    materialName: '废电线',
    materialType: '系统',
    sourceMaterialCode: 'WB00002',
    sourceMaterialName: '佛山黄杂铜',
    source: '富宝资讯',
    templateCode: 'TPL02',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 57270,
    offset: -5800,
    coefficient: 1.18,
    calcPrice: 60734.6,
    syncStatus: '已同步',
    reviewStatus: '待复核',
    reviewer: '',
    reviewedAt: '',
    rejectReason: ''
  },
  {
    id: 5,
    batchId: 'BAT20261027',
    materialCode: 'XT00005',
    materialName: '混铝铜废电线',
    materialType: '系统',
    sourceMaterialCode: 'WB00002',
    sourceMaterialName: '佛山黄杂铜',
    source: '富宝资讯',
    templateCode: 'TPL02',
    periodStart: '2026-10-19',
    periodEnd: '2026-10-25',
    periodAvg: 57270,
    offset: -11802,
    coefficient: 1.18,
    calcPrice: 53652.24,
    syncStatus: '已同步',
    reviewStatus: '待复核',
    reviewer: '',
    reviewedAt: '',
    rejectReason: ''
  }
]

export const logs = [
  {
    time: '2026-10-29 10:20:08',
    type: '参数修改',
    operator: '王莉洁',
    content:
      '物料计价规则切换：网站物料 WB00001 清远机生铝 → 系统物料 XT00001 铝（调整值0）、XT00002 轻杂铝（-842）、XT00003 铝质车底盘（-4500），统一调价系数1.03',
    ip: '10.0.1.xx'
  },
  {
    time: '2026-10-27 10:16:31',
    type: '行情采集',
    operator: '系统',
    content: '富宝资讯「清远机械生铝」同步完成：快照1条、历史288个交易日（2025-10-27 ~ 2026-10-27）',
    ip: '10.0.1.xx'
  },
  {
    time: '2026-10-27 10:15:40',
    type: '物料映射变更',
    operator: '王莉洁',
    content: '新增WB00001清远机生铝 ↔ 富宝资讯「机械生铝」映射关系',
    ip: '10.0.1.xx'
  }
]

export const apiCallLogs = [
  {
    time: '2026-10-27 15:43:25',
    mode: 'daily',
    purpose: '价格分类',
    endpoint: 'https://www.f139.com/visualPane/priceCenterPriceType',
    method: 'GET',
    status: 200,
    elapsed: 574
  },
  {
    time: '2026-10-27 15:43:34',
    mode: 'daily',
    purpose: '当前价格',
    endpoint: 'https://www.f139.com/visualPane/priceCenterDataV3',
    method: 'POST',
    status: 200,
    elapsed: 647
  }
]

export const syncStatus = {
  mode: 'skipped',
  initialized: true,
  initDone: 7,
  initTotal: 7,
  callsToday: 2,
  dailyCap: 20,
  callsRemaining: 18,
  lastResult: 'skipped',
  lastSync: '2026-10-29 09:38:13',
  runSummary: { total: 2, success: 2, partial: 0, failed: 0, skipped: 0 },
  materials: [
    {
      configId: 1,
      materialCode: 'WB00001',
      materialName: '清远机生铝',
      keyword: '机生铝',
      productId: '636',
      status: 'success',
      error: '',
      rows: 289,
      lastDate: '2026-10-28'
    },
    {
      configId: 2,
      materialCode: 'WB00002',
      materialName: '佛山黄杂铜',
      keyword: '黄杂铜',
      productId: '1591',
      status: 'success',
      error: '',
      rows: 287,
      lastDate: '2026-10-28'
    }
  ],
  coverage: { start: '2025-10-27', end: '2026-10-28', days: 289 },
  latest: {
    date: '2026-10-28',
    range: '17,900-18,100',
    avg: 18000,
    change: '平'
  },
  source: {
    name: '富宝资讯',
    material: '清远机械生铝',
    diid: '163321',
    spec: '机生铝 Fe6%-8%',
    tax: '不含税',
    unit: '元/吨'
  }
}

export const marketStats = {
  todayQuotes: 2,
  sourceCount: 3,
  matchedMaterials: 2,
  matchRate: 100,
  unmatched: 0
}

export const demoQuotes = [
  {
    date: '2026-10-28',
    source: '富宝资讯',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    systemName: '清远机生铝（WB00001）',
    materialCode: 'WB00001',
    category: '废金属',
    rawPrice: '17,900-18,100',
    periodAvg: 17883,
    capturedAt: '09:38:13',
    status: '成功'
  },
  {
    date: '2026-10-28',
    source: '富宝资讯',
    externalName: '佛山-黄杂铜-不含税',
    systemName: '佛山黄杂铜（WB00002）',
    materialCode: 'WB00002',
    category: '废金属',
    rawPrice: '57,600-57,700',
    periodAvg: 57450,
    capturedAt: '09:38:13',
    status: '成功'
  }
]

export const collectConfigs = [
  {
    id: 1,
    sourceCode: 'fubao',
    source: '富宝资讯',
    sourceEnabled: true,
    autoSupported: true,
    keyword: '机生铝',
    provinceId: 27,
    provinceName: '广东省',
    cityId: 57,
    cityName: '清远市',
    productId: '636',
    externalName: '清远-机生铝-Fe6%-8%-不含税',
    webName: '机生铝',
    place: '清远',
    spec: 'Fe6%-8%',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    varietyId: 168,
    classifyId: 22,
    materialCode: 'WB00001',
    materialName: '清远机生铝',
    status: '启用',
    historyDays: 365,
    initialized: true,
    historyRows: 289,
    initDone: 7,
    initTotal: 7,
    lastHistoryDate: '2026-10-28',
    lastSnapshotAt: '2026-10-29 09:38:13',
    lastVerifiedAt: '2026-10-27 15:43:00',
    lastError: '',
    remark: '',
    createdAt: '2026-10-27',
    updatedAt: '2026-10-29 09:38:13',
    today: { date: '2026-10-28', range: '17,900-18,100', avg: 18000, change: '平' }
  },
  {
    id: 2,
    sourceCode: 'fubao',
    source: '富宝资讯',
    sourceEnabled: true,
    autoSupported: true,
    keyword: '黄杂铜',
    provinceId: 27,
    provinceName: '广东省',
    cityId: 51,
    cityName: '佛山市',
    productId: '1591',
    externalName: '佛山-黄杂铜-不含税',
    webName: '黄杂铜',
    place: '佛山',
    spec: '',
    tax: '不含税',
    unit: '元/吨',
    org: '富宝废旧',
    varietyId: 482,
    classifyId: 22,
    materialCode: 'WB00002',
    materialName: '佛山黄杂铜',
    status: '启用',
    historyDays: 30,
    initialized: true,
    historyRows: 21,
    initDone: 1,
    initTotal: 1,
    lastHistoryDate: '2026-10-28',
    lastSnapshotAt: '2026-10-29 09:38:13',
    lastVerifiedAt: '2026-10-27 15:43:00',
    lastError: '',
    remark: '',
    createdAt: '2026-10-27',
    updatedAt: '2026-10-29 09:38:13',
    today: { date: '2026-10-28', range: '57,600-57,700', avg: 57650, change: '涨200' }
  }
]

export const collectRegions = {
  provinces: [
    {
      id: 27,
      name: '广东省',
      shortName: '广东',
      cities: [
        { id: 51, name: '佛山市', shortName: '佛山' },
        { id: 57, name: '清远市', shortName: '清远' },
        { id: 91, name: '广州市', shortName: '广州' },
        { id: 175, name: '东莞市', shortName: '东莞' }
      ]
    }
  ],
  updatedAt: '',
  warning: '本地演示数据'
}

export const sourceSync = [
  {
    id: 1,
    code: 'fubao',
    name: '富宝资讯',
    enabled: true,
    autoSupported: true,
    syncMode: 'daily',
    dailyCap: 20,
    lastSyncAt: '2026-10-28 10:26:57',
    lastError: '',
    materialCount: 2,
    enabledCount: 2,
    disabledCount: 0,
    initializedCount: 2,
    errorCount: 0,
    syncedToday: 2
  },
  {
    id: 2,
    code: 'lingtong',
    name: '灵通平台',
    enabled: false,
    autoSupported: false,
    syncMode: 'manual',
    dailyCap: 0,
    lastSyncAt: '',
    lastError: '',
    materialCount: 0,
    enabledCount: 0,
    disabledCount: 0,
    initializedCount: 0,
    errorCount: 0,
    syncedToday: 0
  },
  {
    id: 3,
    code: 'zhongfei',
    name: '中废网',
    enabled: false,
    autoSupported: false,
    syncMode: 'manual',
    dailyCap: 0,
    lastSyncAt: '',
    lastError: '',
    materialCount: 0,
    enabledCount: 0,
    disabledCount: 0,
    initializedCount: 0,
    errorCount: 0,
    syncedToday: 0
  }
]
