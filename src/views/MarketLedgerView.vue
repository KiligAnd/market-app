<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import SyncBanner from '../components/SyncBanner.vue'
import StatCard from '../components/StatCard.vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const stats = computed(() => store.state.marketStats)

const sourceFilter = ref('')
const categoryFilter = ref('')
const startDate = ref('')
const endDate = ref('')
const keyword = ref('')
const jumpPage = ref('')
const pageSize = ref(store.state.ledger.pageSize)

const rows = computed(() => store.state.ledger.items)
const page = computed(() => store.state.ledger.page)
const total = computed(() => store.state.ledger.total)
const totalPages = computed(() => store.state.ledger.totalPages)
const loading = computed(() => store.state.ledger.loading)
const syncing = computed(() => store.state.syncing)
const quota = computed(() => store.state.syncStatus || {})
const quotaExhausted = computed(
  () => quota.value.callsRemaining !== undefined && Number(quota.value.callsRemaining) <= 0
)
const quotaHint = computed(() => {
  if (quota.value.dailyCap === undefined) return ''
  return `今日接口调用 ${quota.value.callsToday || 0} / ${quota.value.dailyCap} 次（剩余 ${quota.value.callsRemaining || 0} 次）`
})

const visiblePages = computed(() => {
  const last = totalPages.value
  const current = page.value
  const start = Math.max(1, Math.min(current - 2, last - 4))
  const end = Math.min(last, start + 4)
  const pages = []
  for (let index = start; index <= end; index += 1) pages.push(index)
  return pages
})

function currentQuery(overrides = {}) {
  const query = {
    page: overrides.page ?? page.value,
    pageSize: pageSize.value,
    source: sourceFilter.value,
    category: categoryFilter.value,
    startDate: startDate.value,
    endDate: endDate.value,
    keyword: keyword.value.trim()
  }
  if (query.startDate && query.endDate && query.startDate > query.endDate) {
    ;[query.startDate, query.endDate] = [query.endDate, query.startDate]
    startDate.value = query.startDate
    endDate.value = query.endDate
  }
  return query
}

function reload(resetPage = false) {
  return store.loadLedger(currentQuery({ page: resetPage ? 1 : page.value }))
}

// 涨跌：涨/跌着色，平与缺失不高亮
function changeClass(text) {
  const value = String(text || '')
  if (value.startsWith('涨')) return 'text-up'
  if (value.startsWith('跌')) return 'text-down'
  return ''
}

let filterTimer = null
let skipWatch = false

watch([sourceFilter, categoryFilter, startDate, endDate, keyword], () => {
  if (skipWatch) {
    skipWatch = false
    return
  }
  clearTimeout(filterTimer)
  filterTimer = setTimeout(() => reload(true), 300)
})

watch(pageSize, () => reload(true))

onMounted(() => reload(true))

function resetFilters() {
  skipWatch = true
  sourceFilter.value = ''
  categoryFilter.value = ''
  startDate.value = ''
  endDate.value = ''
  keyword.value = ''
  reload(true)
}

function goPage(target) {
  const value = Math.min(Math.max(Number(target) || 1, 1), totalPages.value)
  if (value === page.value) return
  store.loadLedger(currentQuery({ page: value }))
}

function jumpToPage() {
  goPage(jumpPage.value)
  jumpPage.value = ''
}

async function manualCollect() {
  if (quotaExhausted.value) {
    store.notify('今日接口配额已用完，请明天再试')
    return
  }
  if (syncing.value) {
    store.notify('采集任务正在运行，请稍后')
    return
  }
  if (!window.confirm('立即采集行情？将按低频策略抓取当前启用的网站物料。')) return
  await store.runCollectNow()
}
</script>

<template>
  <div class="breadcrumb">首页 / 行情管理 / <span>行情数据台账</span></div>
  <div class="page-title">行情数据台账</div>

  <SyncBanner />

  <div class="stats-row">
    <StatCard label="今日采集行情条数" :value="stats.todayQuotes" sub="按行情日期统计" />
    <StatCard label="已对接行情源" :value="stats.sourceCount" sub="富宝 / 灵通 / 中废网" />
    <StatCard label="匹配成功物料数" :value="stats.matchedMaterials" :sub="`匹配率 ${stats.matchRate}%`" />
    <StatCard label="未匹配异常数据" :value="stats.unmatched" sub="待处理" sub-color="#e65100" />
  </div>

  <div class="card">
    <div class="filter-bar">
      <label>行情源：</label>
      <select v-model="sourceFilter">
        <option value="">全部</option>
        <option v-for="source in store.state.sources" :key="source.id" :value="source.code">
          {{ source.name }}
        </option>
      </select>

      <label>物料品类：</label>
      <select v-model="categoryFilter">
        <option value="">全部</option>
        <option value="废金属">废金属</option>
      </select>

      <label>日期范围：</label>
      <input v-model="startDate" type="date" />
      <span class="date-sep">至</span>
      <input v-model="endDate" type="date" />

      <label>关键词：</label>
      <input v-model="keyword" placeholder="物料名称 / 网站物料全称" />

      <button class="btn btn-default btn-sm" @click="resetFilters">重置</button>
      <button class="btn btn-default btn-sm" :disabled="loading" @click="reload(false)">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
      <button
        class="btn btn-primary btn-sm action-right"
        :disabled="syncing || quotaExhausted"
        :title="quotaExhausted ? '今日接口配额已用完，请明天再试' : quotaHint"
        @click="manualCollect"
      >
        {{ syncing ? '采集中…' : '手动采集行情' }}
      </button>
    </div>

    <div class="form-hint">
      按行情日期倒序展示，支持日期范围筛选；每页条数会自动记住。
      「价格」为富宝报价区间，「当日平均价」为当日区间中值；「采集时间」为真实抓取时刻，历史回补行显示「历史回补」。
      <span v-if="quotaHint">· {{ quotaHint }}</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>行情日期</th>
            <th>行情来源</th>
            <th>网站物料名称</th>
            <th>价格</th>
            <th>当日平均价</th>
            <th>涨跌</th>
            <th>采集时间</th>
            <th>采集状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.date }}</td>
            <td>{{ row.source }}</td>
            <td>{{ row.externalName }}</td>
            <td>{{ row.range || '—' }}</td>
            <td>{{ store.formatPrice2(row.avg) }}</td>
            <td :class="changeClass(row.change)">{{ row.change || '—' }}</td>
            <td>{{ row.capturedAt || '历史回补' }}</td>
            <td>
              <StatusTag :text="row.status" :type="row.status === '未匹配' ? 'warning' : 'success'" />
            </td>
          </tr>
          <tr v-if="loading && !rows.length">
            <td colspan="8" class="empty-cell">加载中…</td>
          </tr>
          <tr v-else-if="!loading && !rows.length">
            <td colspan="8" class="empty-cell">没有符合筛选条件的行情数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="pager">
      <span class="page-total">共 {{ total }} 条</span>
      <label>每页</label>
      <select v-model.number="pageSize">
        <option :value="10">10</option>
        <option :value="20">20</option>
        <option :value="50">50</option>
        <option :value="100">100</option>
      </select>
      <span>条</span>

      <button class="page-btn" :disabled="page <= 1 || loading" @click="goPage(1)">首页</button>
      <button class="page-btn" :disabled="page <= 1 || loading" @click="goPage(page - 1)">上一页</button>
      <button
        v-for="item in visiblePages"
        :key="item"
        class="page-btn"
        :class="{ active: item === page }"
        :disabled="loading"
        @click="goPage(item)"
      >
        {{ item }}
      </button>
      <button class="page-btn" :disabled="page >= totalPages || loading" @click="goPage(page + 1)">
        下一页
      </button>
      <button class="page-btn" :disabled="page >= totalPages || loading" @click="goPage(totalPages)">
        末页
      </button>

      <span class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
      <input
        v-model="jumpPage"
        class="page-jump"
        type="number"
        min="1"
        :max="totalPages"
        placeholder="页码"
        @keyup.enter="jumpToPage"
      />
      <button class="page-btn" :disabled="loading" @click="jumpToPage">跳转</button>
    </div>
  </div>
</template>

<style scoped>
.date-sep {
  color: #7b8ea6;
  font-size: 12px;
}

.pager {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eef4fa;
  font-size: 13px;
  color: #4a5f75;
}

.page-total {
  margin-right: 6px;
  color: #7b8ea6;
}

.pager select {
  width: 72px;
}

.page-btn {
  min-width: 32px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  background: #fff;
  color: #4a5f75;
  font-size: 12px;
  cursor: pointer;
}

.page-btn.active {
  background: #1e88e5;
  border-color: #1e88e5;
  color: #fff;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  margin-left: 4px;
  color: #7b8ea6;
}

.page-jump {
  width: 64px;
  height: 28px;
  padding: 0 6px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-size: 12px;
}
</style>
