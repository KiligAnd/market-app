<script setup>
import { computed } from 'vue'
import StatCard from '../components/StatCard.vue'
import TrendChart from '../components/TrendChart.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const dash = computed(() => store.dashboard)
const stats = computed(() => dash.value.stats)

const weekSub = computed(() => {
  if (!stats.value || stats.value.changePct === null) return '—'
  const pct = stats.value.changePct
  return `${pct >= 0 ? '↑' : '↓'} 较上周 ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
})
const weekColor = computed(() => {
  if (!stats.value || stats.value.changePct === null) return '#999'
  return stats.value.changePct >= 0 ? '#2e7d32' : '#c62828'
})
const calcSub = computed(() => {
  if (!stats.value) return '—'
  if (stats.value.offset === null || stats.value.offset === undefined) {
    return '尚未配置公司系统物料'
  }
  return `${stats.value.ruleCount} 个系统物料 · 首条：调整值 ${store.formatSigned(stats.value.offset)} / 系数 ${Number(stats.value.coefficient ?? 1).toFixed(2)}`
})
</script>

<template>
  <div class="breadcrumb">首页 / 数据看板 / <span>行情价格看板</span></div>
  <div class="page-title">行情价格趋势看板</div>

  <div class="card">
    <div class="filter-bar">
      <label>选择物料：</label>
      <select v-model="store.state.dashboardMaterial">
        <option
          v-for="item in store.dashboardMaterials"
          :key="item.code"
          :value="item.code"
        >
          {{ item.code }} {{ item.name }}
        </option>
      </select>

      <label>时间范围：</label>
      <select v-model.number="store.state.dashboardRange">
        <option :value="30">近30天</option>
        <option :value="90">近3个月</option>
        <option :value="180">近半年</option>
      </select>
    </div>

    <div class="chart-wrap">
      <div class="chart-head">
        <div class="chart-legend">
          <span class="dot"></span>
          <template v-if="dash.hasData">
            {{ dash.source.name }} · {{ dash.source.material }}（{{ dash.source.spec }}）行情均价
            <span class="src">{{ dash.source.tax }} · {{ dash.source.unit }}</span>
          </template>
          <template v-else>行情源：— <span class="src">该物料尚未接入行情</span></template>
        </div>
        <div class="chart-range">{{ dash.rangeLabel }}</div>
      </div>

      <TrendChart v-if="dash.hasData && dash.series.length" :series="dash.series" />
      <div v-else class="chart-empty">该物料尚未接入行情数据</div>

      <div class="chart-note">
        <template v-if="dash.hasData">
          数据来源：{{ dash.source.name }}（f139.com）；统计区间
          {{ dash.coverage.start }} ~ {{ dash.coverage.end }}（{{ dash.coverage.days }} 个交易日）。周均价 = 上一完整周（{{ dash.week?.start }} ~ {{ dash.week?.end }}，周一至周五报价）的算术平均；计算售价 =（周均价 + 固定调整值）× 调价系数，保留两位小数。
        </template>
        <template v-else>
          已接入 {{ store.state.collectConfigs.length }} 条网站物料采集配置；可在「网站物料采集配置」新增物料，回补历史后即可展示。
        </template>
      </div>
    </div>
  </div>

  <div class="stats-row">
    <StatCard
      label="本周均价"
      :value="stats ? store.formatPrice2(stats.weekAvg) : '—'"
      :sub="weekSub"
      :sub-color="weekColor"
    />
    <StatCard
      label="本周计算售价（首条规则）"
      :value="stats ? store.formatPrice2(stats.calcPrice) : '—'"
      :sub="calcSub"
    />
    <StatCard
      label="历史最高价"
      :value="stats ? store.formatPrice(stats.high.avg) : '—'"
      :sub="stats ? stats.high.date : '—'"
    />
    <StatCard
      label="历史最低价"
      :value="stats ? store.formatPrice(stats.low.avg) : '—'"
      :sub="stats ? stats.low.date : '—'"
    />
  </div>
</template>
