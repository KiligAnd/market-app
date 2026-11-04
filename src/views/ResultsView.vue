<script setup>
import { computed, ref } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'
import {
  buildPricingReportWorkbook,
  collectReportPeriods,
  displayRangeText,
  executionWeekStart,
  resolveReportRange,
  startOfWeek,
  toIso,
  workbookBlob
} from '../utils/pricingReport'

const store = useMarketStore()
const batchFilter = ref('全部')
const materialFilter = ref('')
const reviewFilter = ref('全部')
const detailRow = ref(null)

const currentWeekStart = startOfWeek(new Date())
const currentWeekKey = toIso(currentWeekStart)
const lastWeekStart = new Date(currentWeekStart)
lastWeekStart.setDate(lastWeekStart.getDate() - 7)
const weekFilter = ref(currentWeekKey)

const exportOpen = ref(false)
const exportGranularity = ref('week')
const exportPreset = ref('thisWeek')
const exportCustomDate = ref(toIso(new Date()))
const exportCustomMonth = ref(toIso(new Date()).slice(0, 7))
const exportBusy = ref(false)

const exportRange = computed(() =>
  resolveReportRange(
    exportGranularity.value,
    exportPreset.value,
    exportGranularity.value === 'week' ? exportCustomDate.value : exportCustomMonth.value
  )
)
const exportPeriods = computed(() =>
  collectReportPeriods(store.state.results, exportRange.value, exportGranularity.value)
)
const exportRowCount = computed(() =>
  exportPeriods.value.reduce((sum, period) => sum + period.rows.length, 0)
)
const exportRangeLabel = computed(() => {
  const range = exportRange.value
  if (range.granularity === 'month') {
    return `${range.start.getFullYear()}年${range.start.getMonth() + 1}月`
  }
  return displayRangeText(range.start, range.end)
})
const exportPriceRangeLabel = computed(() => {
  const range = exportRange.value
  if (range.granularity === 'month') return '各执行周的前一周（周一至周五）'
  const priceStart = new Date(range.start)
  priceStart.setDate(priceStart.getDate() - 7)
  const priceEnd = new Date(range.end)
  priceEnd.setDate(priceEnd.getDate() - 7)
  return displayRangeText(priceStart, priceEnd)
})
const exportSheetLabel = computed(() => {
  if (exportGranularity.value === 'week') return '1 个执行周'
  return `${exportPeriods.value.length} 个执行周`
})

function openExportModal() {
  exportOpen.value = true
  exportGranularity.value = 'week'
  exportPreset.value = 'thisWeek'
}

function closeExportModal() {
  exportOpen.value = false
}

function changeGranularity(value) {
  exportGranularity.value = value
  exportPreset.value = value === 'month' ? 'thisMonth' : 'thisWeek'
}

function setExportPreset(preset) {
  exportPreset.value = preset
}

function downloadFile(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function exportExcel() {
  if (!exportRowCount.value || exportBusy.value) {
    store.notify('该周期暂无计价结果，请选择其他周期')
    return
  }
  exportBusy.value = true
  try {
    const { workbook, rowCount } = await buildPricingReportWorkbook({
      periods: exportPeriods.value,
      quotes: store.state.quotes,
      materials: store.state.materials,
      configs: store.state.collectConfigs
    })
    const blob = await workbookBlob(workbook)
    const suffix = exportRangeLabel.value.replace(/[\\/:*?"<>|]/g, '.')
    downloadFile(blob, `定价报表_${exportGranularity.value === 'week' ? '周' : '月'}_${suffix}.xlsx`)
    store.addLog('报表导出', `导出定价报表：${exportRangeLabel.value}，${rowCount} 条`)
    store.notify(`定价报表已导出（${rowCount} 条，${exportSheetLabel.value}）`)
    closeExportModal()
  } catch (error) {
    store.notify(`报表导出失败：${error.message}`)
  } finally {
    exportBusy.value = false
  }
}

function openDetail(row) {
  detailRow.value = row
}

const reviewTypes = {
  待复核: 'info',
  已复核: 'success',
  已驳回: 'warning'
}

const weekOptions = computed(() => {
  const weeks = new Map()
  const counts = new Map()
  const addWeek = (start, tag = '') => {
    if (!start) return
    const key = toIso(start)
    if (!weeks.has(key)) weeks.set(key, { key, start, tag })
  }
  addWeek(currentWeekStart, '本周')
  addWeek(lastWeekStart, '上周')
  store.state.results.forEach((row) => {
    const start = executionWeekStart(row)
    if (!start) return
    const key = toIso(start)
    addWeek(start)
    counts.set(key, (counts.get(key) || 0) + 1)
  })
  return [...weeks.values()]
    .sort((a, b) => b.key.localeCompare(a.key))
    .map((item) => {
      const end = new Date(item.start)
      end.setDate(end.getDate() + 6)
      const count = counts.get(item.key) || 0
      return {
        ...item,
        end,
        count,
        label: `${displayRangeText(item.start, end)}${item.tag ? `（${item.tag}）` : ''}${count ? ` · ${count} 条` : ' · 暂无'}`
      }
    })
})

const weekFilterLabel = computed(() => {
  if (weekFilter.value === 'all') return '全部周'
  return weekOptions.value.find((item) => item.key === weekFilter.value)?.label || weekFilter.value
})

// 「全部批次」下同一系统物料+统计周期只保留最新一条（历史仍保留在批次明细里）
const filteredRows = computed(() => {
  const rows = [...store.state.results].sort((a, b) => b.id - a.id)
  const filtered = rows.filter((row) => {
    if (weekFilter.value !== 'all') {
      const start = executionWeekStart(row)
      if (!start || toIso(start) !== weekFilter.value) return false
    }
    if (batchFilter.value !== '全部' && row.batchId !== batchFilter.value) return false
    if (reviewFilter.value !== '全部' && row.reviewStatus !== reviewFilter.value) return false
    if (!materialFilter.value) return true
    return `${row.materialCode} ${row.materialName} ${row.sourceMaterialCode} ${row.sourceMaterialName}`
      .toLowerCase()
      .includes(materialFilter.value.toLowerCase())
  })
  if (batchFilter.value !== '全部') return filtered
  const seen = new Set()
  return filtered.filter((row) => {
    const key = `${row.materialCode}|${row.periodStart}|${row.periodEnd}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

</script>

<template>
  <div class="breadcrumb">首页 / 计价执行 / <span>计价结果管理</span></div>
  <div class="page-title">计价结果管理</div>

  <div class="card">
    <div class="filter-bar">
      <label>计价批次：</label>
      <select v-model="batchFilter">
        <option>全部</option>
        <option v-for="batch in store.state.batches" :key="batch.id" :value="batch.id">
          {{ batch.id }}
        </option>
      </select>

      <label>计价周：</label>
      <select v-model="weekFilter">
        <option value="all">全部周</option>
        <option v-for="week in weekOptions" :key="week.key" :value="week.key">
          {{ week.label }}
        </option>
      </select>

      <label>物料：</label>
      <input v-model="materialFilter" placeholder="物料编码/名称" />

      <label>复核状态：</label>
      <select v-model="reviewFilter">
        <option>全部</option>
        <option>待复核</option>
        <option>已复核</option>
        <option>已驳回</option>
      </select>

      <button class="btn btn-primary btn-sm action-right" @click="store.batchApprove">批量复核通过</button>
      <button class="btn btn-default btn-sm" @click="openExportModal">导出定价报表</button>
    </div>

    <div class="filter-hint">
      <template v-if="weekFilter !== 'all'">
        计价周：{{ weekFilterLabel }}（按执行周归属，报价取执行周的上一周）。
      </template>
      <template v-else>当前显示全部计价周。</template>
      <template v-if="batchFilter === '全部'">
        同一系统物料 + 统计周期只显示最新一次计价结果（历史批次数据可在「自动计价任务」的批次明细中查看）。
      </template>
      <template v-else>
        当前显示批次 {{ batchFilter }} 的全部明细，不做同周期合并。
      </template>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>网站物料</th>
            <th>系统物料编码</th>
            <th>系统物料名称</th>
            <th>使用模板</th>
            <th>统计周期</th>
            <th>周期均价</th>
            <th>固定调整值</th>
            <th>调价系数</th>
            <th>计算售价</th>
            <th>同步价目表</th>
            <th>复核状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredRows" :key="row.id">
            <td>{{ row.batchId }}</td>
            <td>
              <template v-if="row.sourceMaterialCode">
                {{ row.sourceMaterialCode }}
                <div class="cell-sub">{{ row.sourceMaterialName }}</div>
              </template>
              <span v-else>—</span>
            </td>
            <td>{{ row.materialCode }}</td>
            <td>{{ row.materialName }}</td>
            <td>{{ row.templateCode }}</td>
            <td>{{ row.periodStart ? `${row.periodStart} ~ ${row.periodEnd}` : '—' }}</td>
            <td>{{ store.formatPrice2(row.periodAvg) }}</td>
            <td :class="row.offset > 0 ? 'text-up' : row.offset < 0 ? 'text-down' : ''">
              {{ store.formatAdjust(row.offset) }}
            </td>
            <td>{{ row.coefficient === null ? '—' : Number(row.coefficient).toFixed(2) }}</td>
            <td class="price-cell">{{ store.formatPrice2(row.calcPrice) }}</td>
            <td><StatusTag :text="row.syncStatus" type="success" /></td>
            <td><StatusTag :text="row.reviewStatus" :type="reviewTypes[row.reviewStatus] || 'info'" /></td>
            <td>
              <button class="btn btn-default btn-sm" @click="openDetail(row)">明细</button>
              <template v-if="row.reviewStatus === '待复核'">
                <button class="btn btn-primary btn-sm" @click="store.reviewResult(row.id, '已复核')">通过</button>
                <button class="btn btn-default btn-sm" @click="store.reviewResult(row.id, '已驳回')">驳回</button>
              </template>
            </td>
          </tr>
          <tr v-if="!filteredRows.length">
            <td colspan="13" class="empty-cell">当前计价周没有符合条件的计价结果</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="detailRow" class="card">
    <div class="card-title">
      📋 计价结果明细：{{ detailRow.materialCode }} {{ detailRow.materialName }}
    </div>
    <table class="data-table">
      <tbody>
        <tr>
          <th>批次编号</th>
          <td>{{ detailRow.batchId }}</td>
          <th>使用模板</th>
          <td>{{ detailRow.templateCode }}</td>
        </tr>
        <tr>
          <th>网站物料</th>
          <td>
            {{ detailRow.sourceMaterialCode }} {{ detailRow.sourceMaterialName || '—' }}
          </td>
          <th>行情来源</th>
          <td>{{ detailRow.source || '—' }}</td>
        </tr>
        <tr>
          <th>统计周期</th>
          <td>{{ detailRow.periodStart ? `${detailRow.periodStart} ~ ${detailRow.periodEnd}` : '—' }}</td>
          <th>周期均价</th>
          <td>{{ store.formatPrice2(detailRow.periodAvg) }}</td>
        </tr>
        <tr>
          <th>固定调整值</th>
          <td>{{ store.formatAdjust(detailRow.offset) }}</td>
          <th>调价系数</th>
          <td>{{ detailRow.coefficient === null ? '—' : Number(detailRow.coefficient).toFixed(2) }}</td>
        </tr>
        <tr>
          <th>计算售价</th>
          <td class="price-cell">{{ store.formatPrice2(detailRow.calcPrice) }}</td>
          <th>同步价目表</th>
          <td>{{ detailRow.syncStatus }}</td>
        </tr>
        <tr>
          <th>复核状态</th>
          <td>{{ detailRow.reviewStatus }}</td>
          <th>复核人</th>
          <td>{{ detailRow.reviewer || '—' }}</td>
        </tr>
        <tr>
          <th>复核时间</th>
          <td>{{ detailRow.reviewedAt || '—' }}</td>
          <th>驳回原因</th>
          <td>{{ detailRow.rejectReason || '—' }}</td>
        </tr>
      </tbody>
    </table>
    <div class="form-actions">
      <button class="btn btn-default btn-sm" @click="detailRow = null">关闭</button>
    </div>
  </div>

  <div v-if="exportOpen" class="modal-mask" @click.self="closeExportModal">
    <div class="modal-panel export-modal">
      <div class="modal-head">
        <span>导出定价报表</span>
        <button class="modal-close" @click="closeExportModal">×</button>
      </div>

      <div class="modal-body">
        <div class="form-row">
          <label>导出粒度：</label>
          <label class="export-option">
            <input
              type="radio"
              value="week"
              :checked="exportGranularity === 'week'"
              @change="changeGranularity('week')"
            />
            按周
          </label>
          <label class="export-option">
            <input
              type="radio"
              value="month"
              :checked="exportGranularity === 'month'"
              @change="changeGranularity('month')"
            />
            按月
          </label>
        </div>

        <div v-if="exportGranularity === 'week'" class="form-row">
          <label>快捷周期：</label>
          <div class="preset-row">
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'thisWeek' }"
              @click="setExportPreset('thisWeek')"
            >
              本周
            </button>
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'lastWeek' }"
              @click="setExportPreset('lastWeek')"
            >
              上周
            </button>
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'custom' }"
              @click="setExportPreset('custom')"
            >
              自定义周
            </button>
            <input v-if="exportPreset === 'custom'" v-model="exportCustomDate" type="date" />
          </div>
        </div>

        <div v-else class="form-row">
          <label>快捷周期：</label>
          <div class="preset-row">
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'thisMonth' }"
              @click="setExportPreset('thisMonth')"
            >
              本月
            </button>
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'lastMonth' }"
              @click="setExportPreset('lastMonth')"
            >
              上月
            </button>
            <button
              class="btn btn-default btn-sm preset-btn"
              :class="{ active: exportPreset === 'custom' }"
              @click="setExportPreset('custom')"
            >
              自定义月
            </button>
            <input v-if="exportPreset === 'custom'" v-model="exportCustomMonth" type="month" />
          </div>
        </div>

        <div class="export-summary">
          <div class="export-summary-row">
            <span>报表周期</span>
            <strong>{{ exportRangeLabel }}</strong>
          </div>
          <div class="export-summary-row">
            <span>取价周期</span>
            <strong>{{ exportPriceRangeLabel }}</strong>
            <small>只取周一至周五报价计算网络平均价</small>
          </div>
          <div class="export-summary-row">
            <span>可导出</span>
            <strong>{{ exportRowCount }} 条 · {{ exportSheetLabel }}</strong>
          </div>
        </div>

        <div v-if="!exportRowCount" class="warn-box">
          该周期暂无计价结果。计价结果按「执行周」归属，报价取执行周的上一周；请选择其他周期。
        </div>

        <div class="form-hint">
          导出按周期取全部计价结果（同一系统物料 + 统计周期只取最新一条），不受上方批次/物料/复核筛选影响。
          格式按「品种经销价格推算」模板：类别、标的物、序号、品名、单位、周一至周五、
          网络平均价、固定系数、底标价、中标系数、执行价、浮动率来源。
          <template v-if="exportGranularity === 'month'">按月导出时，每个执行周生成一个工作表。</template>
        </div>
      </div>

      <div class="modal-foot">
        <button class="btn btn-default" @click="closeExportModal">取消</button>
        <button class="btn btn-primary" :disabled="exportBusy || !exportRowCount" @click="exportExcel">
          {{ exportBusy ? '生成中…' : '导出 Excel' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(26, 58, 92, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 32px 16px;
  overflow: auto;
  z-index: 50;
}

.modal-panel {
  width: 100%;
  max-width: 680px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 12px 36px rgba(26, 58, 92, 0.25);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #e8f0f8;
  font-size: 16px;
  font-weight: 600;
  color: #1a3a5c;
}

.modal-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #8aa0b6;
  cursor: pointer;
}

.modal-body {
  padding: 16px 20px;
}

.modal-body .form-row > label {
  width: 90px;
  flex: 0 0 90px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e8f0f8;
}

.export-option {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-right: 18px;
  font-size: 13px;
  color: #4a5f75;
  cursor: pointer;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.preset-btn.active {
  border-color: #1e88e5;
  background: #eef7ff;
  color: #1e88e5;
}

.export-summary {
  margin: 14px 0;
  padding: 12px 14px;
  border: 1px solid #dbeaf9;
  border-radius: 6px;
  background: #f8fbff;
}

.export-summary-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  color: #4a5f75;
}

.export-summary-row > span {
  width: 72px;
  flex: 0 0 72px;
  color: #7b8ea6;
}

.export-summary-row strong {
  color: #1a3a5c;
}

.export-summary-row small {
  color: #8aa0b6;
}

.warn-box {
  margin: 10px 0;
  padding: 8px 10px;
  border: 1px solid #ffe0b2;
  border-radius: 4px;
  background: #fff7ed;
  color: #e65100;
  font-size: 12px;
  line-height: 1.6;
}
</style>
