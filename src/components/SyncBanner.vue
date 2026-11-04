<script setup>
import { computed } from 'vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const sync = computed(() => store.state.syncStatus)

const modeInfo = computed(() => {
  if (!sync.value.initialized) return { label: '初始化回补中', className: 'mode-init' }
  if (sync.value.mode === 'error') return { label: '同步失败', className: 'mode-error' }
  if (sync.value.mode === 'partial') return { label: '部分物料未同步', className: 'mode-partial' }
  if (sync.value.mode === 'skipped') return { label: '今日已同步', className: 'mode-skip' }
  return { label: '每日增量', className: 'mode-daily' }
})

const bannerClass = computed(() => {
  if (sync.value.mode === 'error') return 'banner-error'
  if (sync.value.mode === 'partial') return 'banner-partial'
  if (sync.value.mode === 'skipped') return 'banner-skip'
  return ''
})

const runSummary = computed(() => sync.value.runSummary || {})

const bannerTitle = computed(() => {
  if (!sync.value.initialized) return '⏳ 初始化回补中'
  if (sync.value.mode === 'error') {
    const total = runSummary.value.total || 0
    const failed = (runSummary.value.failed || 0) + (runSummary.value.skipped || 0)
    return total > 1 ? `⚠ 同步失败（${failed}/${total} 个物料未完成）` : '⚠ 同步失败'
  }
  if (sync.value.mode === 'partial') {
    const total = runSummary.value.total || 0
    const bad = (runSummary.value.failed || 0) + (runSummary.value.partial || 0) +
      (runSummary.value.skipped || 0)
    return `⚠ 部分物料未同步（${bad}/${total}）`
  }
  if (sync.value.mode === 'skipped') return '⏸ 今日已同步（未重复调用接口）'
  return '🔄 每日增量已同步'
})

const timePrefix = computed(() => (sync.value.mode === 'skipped' ? '最近同步' : '同步时间'))
const lastSyncText = computed(() => sync.value.lastSync || '—')
const initProgress = computed(
  () => `${sync.value.initDone}/${sync.value.initTotal} 个窗口`
)
const coverage = computed(
  () =>
    `${sync.value.coverage.start} ~ ${sync.value.coverage.end}（${sync.value.coverage.days} 个交易日）`
)
const failedItems = computed(() =>
  (sync.value.materials || []).filter((item) => item.error)
)
const quotaText = computed(() => {
  const cap = sync.value.dailyCap || 0
  const used = sync.value.callsToday || 0
  return cap ? `${used} / ${cap} 次` : `${used} 次`
})
</script>

<template>
  <div class="sync-banner" :class="bannerClass">
    <span>{{ bannerTitle }}</span>
    <span class="sync-time">
      富宝资讯 · {{ sync.source.material }} · {{ timePrefix }}
      {{ lastSyncText }} · 历史 {{ sync.coverage.days }} 个交易日
    </span>
    <span class="sync-latest">
      最新 {{ sync.latest.date || '—' }}：{{ sync.latest.range }} 元/吨（均价
      {{ store.formatPrice(sync.latest.avg) }}，{{ sync.latest.change }}）
    </span>
  </div>

  <div v-if="failedItems.length" class="sync-error">
    <div v-for="item in failedItems" :key="item.configId" class="sync-error-row">
      <span class="sync-error-name">{{ item.materialCode }} {{ item.materialName }}</span>
      <span class="sync-error-reason" :title="item.error">{{ item.error }}</span>
    </div>
  </div>

  <div class="sync-status">
    <span class="sync-mode" :class="modeInfo.className">{{ modeInfo.label }}</span>
    <span><span class="sync-key">初始化：</span>{{ initProgress }}</span>
    <span>
      <span class="sync-key">今日接口调用：</span>{{ quotaText }}
      <span v-if="sync.callsRemaining !== undefined" class="sync-key">
        （剩余 {{ sync.callsRemaining }} 次）
      </span>
    </span>
    <span><span class="sync-key">数据覆盖：</span>{{ coverage }}</span>
  </div>
</template>
