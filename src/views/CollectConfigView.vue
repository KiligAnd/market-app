<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AppSelect from '../components/AppSelect.vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()

const keyword = ref('')
const statusFilter = ref('全部')
const showForm = ref(false)
const editingId = ref(null)
const searching = ref(false)
const saving = ref(false)
const candidates = ref([])
const searchInfo = ref('')
const activeSourceCode = ref('')

const form = reactive({
  source: 'fubao',
  keyword: '',
  provinceId: '',
  provinceName: '',
  cityId: '',
  cityName: '',
  productId: '',
  externalName: '',
  externalWebName: '',
  externalPlace: '',
  externalSpec: '',
  externalTax: '',
  externalUnit: '元/吨',
  externalOrg: '',
  varietyId: null,
  classifyId: null,
  materialCode: '',
  historyDays: 30,
  remark: '',
  enabled: true
})

// 编辑时记录打开时的回补天数，用于判断是否“调大”
const originalHistoryDays = ref(0)
const historyExpanded = computed(
  () => !!editingId.value && Number(form.historyDays || 0) > originalHistoryDays.value
)

const sourceOptions = computed(() =>
  store.state.sources.map((item) => ({
    code: item.code || item.id,
    name: item.name
  }))
)

const provinces = computed(() => store.state.regions.provinces || [])

const collectToken = computed(() => store.state.collectToken || {})
const tokenInput = ref('')
const tokenSaving = ref(false)
const accountModalOpen = ref(false)
const showTokenForm = ref(false)
const credentialSaving = ref(false)
const credentialRefreshing = ref(false)
const credentialForm = reactive({ username: '', password: '' })
const autoRenew = computed(() => Boolean(collectToken.value.autoRenew))

const tokenRemaining = computed(() => {
  const hours = collectToken.value.remainingHours
  if (hours === null || hours === undefined) return ''
  if (hours <= 0) return '已过期'
  if (hours < 24) return `剩余约 ${hours} 小时`
  const days = Math.floor(hours / 24)
  const rest = hours % 24
  return `剩余约 ${days} 天${rest ? ` ${rest} 小时` : ''}`
})

async function saveToken() {
  const value = tokenInput.value.trim()
  if (!value) {
    store.notify('请先粘贴富宝 token')
    return
  }
  tokenSaving.value = true
  try {
    await store.saveCollectToken(value)
    tokenInput.value = ''
  } catch (error) {
    store.notify(`保存失败：${error.message}`)
  } finally {
    tokenSaving.value = false
  }
}

async function saveCredentials() {
  const username = credentialForm.username.trim()
  const password = credentialForm.password
  if (!username || !password) {
    store.notify('请输入富宝用户名和密码')
    return
  }
  credentialSaving.value = true
  try {
    await store.saveCollectCredentials(username, password)
    credentialForm.username = ''
    credentialForm.password = ''
    accountModalOpen.value = false
  } catch (error) {
    store.notify(`账号登录失败：${error.message}`)
  } finally {
    credentialSaving.value = false
  }
}

function openAccountModal() {
  accountModalOpen.value = true
  showTokenForm.value = false
  credentialForm.password = ''
}

function closeAccountModal() {
  accountModalOpen.value = false
  showTokenForm.value = false
  credentialForm.password = ''
}

async function refreshTokenNow() {
  credentialRefreshing.value = true
  try {
    await store.refreshCollectToken()
  } catch (error) {
    store.notify(`续期失败：${error.message}`)
  } finally {
    credentialRefreshing.value = false
  }
}

async function removeCredentials() {
  if (!window.confirm('退出账号后 token 到期将无法自动续期，确认退出？')) return
  try {
    await store.deleteCollectCredentials()
    accountModalOpen.value = false
    showTokenForm.value = false
  } catch (error) {
    store.notify(`退出失败：${error.message}`)
  }
}

const historyHint = computed(() => {
  const days = Math.max(1, Math.min(Number(form.historyDays) || 30, 365))
  const end = new Date()
  const start = new Date(end.getTime() - days * 86400000)
  const fmt = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  const windows = Math.max(1, Math.ceil((days + 1) / 60))
  return `同步 ${fmt(start)} ~ ${fmt(end)}，约 ${windows} 个窗口（${windows} 次接口调用）`
})

const cities = computed(() => {
  const province = provinces.value.find(
    (item) => String(item.id) === String(form.provinceId)
  )
  return province ? province.cities : []
})

const selectedProvince = computed(() =>
  provinces.value.find((item) => String(item.id) === String(form.provinceId))
)

const filteredConfigs = computed(() => {
  if (!activeSource.value) return []
  return store.state.collectConfigs.filter((row) => {
    if (row.sourceCode !== activeSource.value.code || row.status === '已删除') return false
    if (statusFilter.value !== '全部' && row.status !== statusFilter.value) return false
    if (!keyword.value) return true
    const text = `${row.keyword} ${row.externalName} ${row.materialCode} ${row.productId}`.toLowerCase()
    return text.includes(keyword.value.toLowerCase())
  })
})

const selectedCandidate = computed(
  () => candidates.value.find((item) => item.productId === form.productId) || null
)

function todayText() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const sourceCards = computed(() =>
  store.state.sourceSync.map((source) => {
    const configs = store.state.collectConfigs.filter(
      (item) => item.sourceCode === source.code && item.status !== '已删除'
    )
    const today = todayText()
    const lastSyncAt =
      configs
        .map((item) => item.lastSnapshotAt || '')
        .sort()
        .pop() || source.lastSyncAt || ''
    return {
      ...source,
      configs,
      materialCount: configs.length,
      enabledCount: configs.filter((item) => item.status === '启用').length,
      disabledCount: configs.filter((item) => item.status === '停用').length,
      syncedToday: configs.filter(
        (item) => (item.lastSnapshotAt || '').slice(0, 10) === today
      ).length,
      errorCount: configs.filter((item) => item.lastError).length,
      lastSyncAt
    }
  })
)

const activeSource = computed(() =>
  sourceCards.value.find((item) => item.code === activeSourceCode.value) || sourceCards.value[0] || null
)

watch(
  sourceCards,
  (list) => {
    if (!list.length) return
    if (!list.some((item) => item.code === activeSourceCode.value)) {
      activeSourceCode.value = (list.find((item) => item.materialCount > 0) || list[0]).code
    }
  },
  { immediate: true }
)

const sourceSelectOptions = computed(() =>
  sourceCards.value.map((item) => ({
    value: item.code,
    label: `${item.name}（${item.materialCount}）`,
    tag: item.autoSupported ? '' : '未接入'
  }))
)

const statusSelectOptions = [
  { value: '全部', label: '全部' },
  { value: '启用', label: '启用' },
  { value: '停用', label: '停用' }
]

const formSourceOptions = computed(() =>
  sourceOptions.value.map((item) => ({ value: item.code, label: item.name }))
)

const provinceSelectOptions = computed(() => [
  { value: '', label: '请选择省 / 直辖市' },
  ...provinces.value.map((item) => ({ value: item.id, label: item.name }))
])

const citySelectOptions = computed(() => [
  { value: '', label: '不限（按省匹配）' },
  ...cities.value.map((item) => ({ value: item.id, label: item.name }))
])

function resetForm() {
  originalHistoryDays.value = 0
  Object.assign(form, {
    source: 'fubao',
    keyword: '',
    provinceId: '',
    provinceName: '',
    cityId: '',
    cityName: '',
    productId: '',
    externalName: '',
    externalWebName: '',
    externalPlace: '',
    externalSpec: '',
    externalTax: '',
    externalUnit: '元/吨',
    externalOrg: '',
    varietyId: null,
    classifyId: null,
    materialCode: '',
    historyDays: 30,
    remark: '',
    enabled: true
  })
  candidates.value = []
  searchInfo.value = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  showForm.value = true
  if (!provinces.value.length) store.loadRegions(false)
}

function openEdit(row) {
  editingId.value = row.id
  originalHistoryDays.value = Number(row.historyDays || 0)
  Object.assign(form, {
    source: row.sourceCode,
    keyword: row.keyword,
    provinceId: row.provinceId,
    provinceName: row.provinceName,
    cityId: row.cityId,
    cityName: row.cityName,
    productId: row.productId,
    externalName: row.externalName,
    externalWebName: row.webName,
    externalPlace: row.place,
    externalSpec: row.spec,
    externalTax: row.tax,
    externalUnit: row.unit || '元/吨',
    externalOrg: row.org,
    varietyId: row.varietyId,
    classifyId: row.classifyId,
    materialCode: row.materialCode || '',
    historyDays: row.historyDays || 30,
    remark: row.remark || '',
    enabled: row.status === '启用'
  })
  candidates.value = []
  searchInfo.value = ''
  showForm.value = true
}

function onProvinceChange() {
  const province = selectedProvince.value
  form.provinceName = province ? province.name : ''
  form.cityId = ''
  form.cityName = ''
}

function onCityChange() {
  const city = cities.value.find((item) => String(item.id) === String(form.cityId))
  form.cityName = city ? city.name : ''
}

function onSourceChange() {
  const source = sourceOptions.value.find((item) => item.code === form.source)
  if (source) form.source = source.code
}

async function doSearch() {
  if (!form.keyword.trim()) {
    store.notify('请输入网站物料名称，如 机生铝 / 黄杂铜')
    return
  }
  if (!form.provinceId) {
    store.notify('请先选择省/直辖市')
    return
  }
  searching.value = true
  try {
    const data = await store.searchCollect({
      source: form.source,
      keyword: form.keyword.trim(),
      provinceId: Number(form.provinceId),
      cityId: form.cityId ? Number(form.cityId) : null,
      pageSize: 50
    })
    candidates.value = data.items || []
    const regionLabel = form.cityId
      ? `${data.province.name || form.provinceName} / ${data.city.name || form.cityName}`
      : `${data.province.name || form.provinceName}（全省）`
    searchInfo.value = `富宝返回 ${data.items.length} 条，共 ${data.total} 条；已按「${regionLabel}」标记地区匹配`
    if (!candidates.value.length) {
      store.notify('没有搜索到该物料，请更换关键词')
    }
  } catch (error) {
    store.notify(`搜索失败：${error.message}`)
  } finally {
    searching.value = false
  }
}

function chooseCandidate(item) {
  form.productId = item.productId
  form.externalName = item.externalName
  form.externalWebName = item.webName
  form.externalPlace = item.place
  form.externalSpec = item.spec
  form.externalTax = item.tax
  form.externalUnit = item.unit || '元/吨'
  form.externalOrg = item.org
  form.varietyId = item.varietyId
  form.classifyId = item.classifyId
}

async function save() {
  if (!form.productId) {
    store.notify('请先搜索并选择一个富宝产品')
    return
  }
  const province = selectedProvince.value
  const city = cities.value.find((item) => String(item.id) === String(form.cityId))
  const payload = {
    source: form.source,
    keyword: form.keyword.trim(),
    provinceId: Number(form.provinceId),
    provinceName: province ? province.name : form.provinceName,
    cityId: form.cityId ? Number(form.cityId) : null,
    cityName: city ? city.name : '',
    productId: form.productId,
    externalName: form.externalName,
    externalWebName: form.externalWebName,
    externalPlace: form.externalPlace,
    externalSpec: form.externalSpec,
    externalTax: form.externalTax,
    externalUnit: form.externalUnit,
    externalOrg: form.externalOrg,
    varietyId: form.varietyId,
    classifyId: form.classifyId,
    historyDays: Number(form.historyDays) || 30,
    remark: form.remark,
    enabled: form.enabled,
    syncHistory: !editingId.value || historyExpanded.value
  }
  saving.value = true
  try {
    const data = await store.saveCollect(editingId.value, payload)
    const configId = data.item.id
    showForm.value = false
    resetForm()
    editingId.value = null
    if (data.backfill && data.backfill.started) startBackfillPolling(configId)
  } catch (error) {
    store.notify(`保存失败：${error.message}`)
  } finally {
    saving.value = false
  }
}

let backfillTimer = null

function startBackfillPolling(configId) {
  clearTimeout(backfillTimer)
  const startedAt = Date.now()
  const tick = async () => {
    await store.refreshCollectConfigs()
    const row = store.state.collectConfigs.find((item) => item.id === configId)
    if (!row) return
    const running = row.backfillRunning ||
      (!row.initialized && row.initTotal > 0 && !row.lastError)
    if (running && Date.now() - startedAt < 30 * 60 * 1000) {
      backfillTimer = setTimeout(tick, 4000)
      return
    }
    if (row.initialized) {
      store.notify(`「${row.keyword}」历史同步完成：${row.historyRows} 个交易日`)
    } else if (row.lastError) {
      store.notify(`「${row.keyword}」历史同步未完成：${row.lastError}`)
    } else if (row.initTotal) {
      store.notify(`「${row.keyword}」历史同步已暂停，明日自动续跑`)
    }
  }
  backfillTimer = setTimeout(tick, 2000)
}

function closeForm() {
  showForm.value = false
  resetForm()
  editingId.value = null
}

async function toggleSourceCard(source) {
  if (!source.autoSupported) {
    store.notify('该网站尚未接入自动解析')
    return
  }
  const action = source.enabled ? '停用' : '启用'
  if (
    !window.confirm(
      `${action}「${source.name}」网站同步？\n停用后其下物料不再参与每日同步，已抓取的历史行情保留。`
    )
  ) {
    return
  }
  try {
    await store.toggleSource(source.id)
  } catch (error) {
    store.notify(error.message)
  }
}

async function batchToggleSource(source, enabled) {
  if (!source.autoSupported) {
    store.notify('该网站尚未接入自动解析')
    return
  }
  if (enabled && !source.enabled) {
    store.notify('网站总开关已关闭，请先启用网站同步')
    return
  }
  const label = enabled ? '启用' : '停用'
  if (
    !window.confirm(
      `确定${label}「${source.name}」下全部 ${source.materialCount} 条物料吗？`
    )
  ) {
    return
  }
  try {
    await store.batchToggle(source.id, enabled)
  } catch (error) {
    store.notify(error.message)
  }
}

function startBackfill(row) {
  const answer = window.prompt(
    `回补多少天历史行情？（1-365，当前配置 ${row.historyDays || 30} 天，已回补 ${row.historyRows || 0} 个交易日；调大只会补更早区间，不会重抓已有数据）`,
    row.historyDays || 30
  )
  if (answer === null) return
  const days = Number(answer)
  if (!days || days < 1 || days > 365) {
    store.notify('请输入 1-365 之间的天数')
    return
  }
  store.backfillCollect(row.id, { days, reinit: false })
}

function remove(row) {
  if (window.confirm(`确定删除采集配置「${row.externalName}」吗？历史行情会保留。`)) {
    store.deleteCollect(row.id)
  }
}

function initLabel(row) {
  if (row.backfillRunning) {
    return row.initTotal ? `同步中 ${row.initDone}/${row.initTotal}` : '同步中…'
  }
  if (row.initialized) return '已完成'
  if (row.lastError) {
    return row.initTotal ? `未完成 ${row.initDone}/${row.initTotal}` : '同步失败'
  }
  if (row.initTotal) return `已暂停 ${row.initDone}/${row.initTotal}`
  return '待同步'
}

onMounted(async () => {
  if (!store.state.loaded) await store.loadAll()
  if (store.state.apiOnline) await store.loadRegions(false)
})
</script>

<template>
  <div class="breadcrumb">首页 / 行情管理 / <span>网站物料采集配置</span></div>
  <div class="page-title">网站物料采集配置</div>

  <div class="card">
    <div class="filter-bar">
      <label>网站：</label>
      <AppSelect
        v-model="activeSourceCode"
        :options="sourceSelectOptions"
        placeholder="请选择网站"
        :disabled="!sourceCards.length"
        style="width: 190px"
      />

      <label>状态：</label>
      <AppSelect
        v-model="statusFilter"
        :options="statusSelectOptions"
        style="width: 110px"
      />
      <label>关键词：</label>
      <input v-model="keyword" placeholder="物料名称 / 网站物料全称" />

      <button class="btn btn-default btn-sm action-right" @click="store.loadRegions(true)">
        刷新省市字典
      </button>
      <button class="btn btn-primary btn-sm" @click="openCreate">
        新增采集配置
      </button>
    </div>

    <div v-if="store.state.regions.warning" class="form-hint">
      {{ store.state.regions.warning }}
    </div>

    <div v-if="activeSource" class="source-card source-panel">
      <div class="source-head">
        <div>
          <div class="source-name">
            {{ activeSource.name }}
            <span v-if="!activeSource.autoSupported" class="status-tag status-warning">未接入自动解析</span>
            <span v-else-if="!activeSource.enabled" class="status-tag status-danger">网站已停用</span>
            <span v-else class="status-tag status-success">同步中</span>
          </div>
          <div class="source-stats">
            物料 {{ activeSource.materialCount }} 条 · 启用 {{ activeSource.enabledCount }} · 停用
            {{ activeSource.disabledCount }} · 今日已同步
            {{ activeSource.syncedToday }}/{{ activeSource.enabledCount }}
          </div>
        </div>
        <label
          class="switch-wrap"
          :title="activeSource.autoSupported ? '网站同步总开关' : '该网站尚未接入自动解析'"
        >
          <input
            type="checkbox"
            :checked="activeSource.enabled"
            :disabled="!activeSource.autoSupported"
            @click.prevent="toggleSourceCard(activeSource)"
          />
          <span class="switch-track"><span class="switch-knob"></span></span>
        </label>
      </div>

      <div class="source-meta">
        <span>最近同步：{{ activeSource.lastSyncAt || '—' }}</span>
        <span v-if="activeSource.dailyCap">
          今日接口 {{ activeSource.callsToday || 0 }}/{{ activeSource.dailyCap }} 次
        </span>
        <span v-if="activeSource.callsRemaining === 0" class="text-warn">今日配额已用完</span>
        <span v-if="activeSource.errorCount" class="text-warn">
          异常 {{ activeSource.errorCount }} 条
        </span>
      </div>

      <div
        v-if="activeSource.code === 'fubao'"
        class="source-account"
        role="button"
        tabindex="0"
        @click="openAccountModal"
        @keyup.enter="openAccountModal"
      >
        <span class="source-account-title">用户账号</span>
        <span v-if="autoRenew" class="source-account-name">{{ collectToken.autoRenewAccount }}</span>
        <span v-else class="text-warn">未登录</span>
        <span class="form-hint source-account-token">
          <template v-if="collectToken.valid">
            token 有效至 {{ collectToken.expiry }}
            <template v-if="tokenRemaining">（{{ tokenRemaining }}）</template>
          </template>
          <template v-else-if="collectToken.present">token 已过期</template>
          <template v-else>点击登录富宝账号</template>
        </span>
        <span class="source-account-link">查看 / 登录 ›</span>
      </div>

      <div class="source-actions">
        <button
          class="btn btn-default btn-sm"
          :disabled="!activeSource.autoSupported || !activeSource.enabled || !activeSource.materialCount"
          @click="batchToggleSource(activeSource, true)"
        >
          全部启用
        </button>
        <button
          class="btn btn-default btn-sm"
          :disabled="!activeSource.autoSupported || !activeSource.materialCount"
          @click="batchToggleSource(activeSource, false)"
        >
          全部停用
        </button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>网站物料名称</th>
            <th>省 / 市</th>
            <th>网站物料全称</th>
            <th>网站物料</th>
            <th>状态</th>
            <th>历史回补</th>
            <th>最近同步</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredConfigs" :key="row.id">
            <td>{{ row.keyword }}</td>
            <td>{{ row.provinceName }} / {{ row.cityName || '不限' }}</td>
            <td>
              <div>{{ row.externalName }}</div>
              <div class="cell-sub">{{ row.place }} · {{ row.spec || '—' }} · {{ row.tax || '—' }}</div>
            </td>
            <td>
              <div v-if="row.materialCode">{{ row.materialCode }} {{ row.materialName }}</div>
              <span v-else class="text-warn">未绑定</span>
            </td>
            <td>
              <StatusTag
                :text="row.status"
                :type="row.status === '启用' ? 'success' : row.status === '停用' ? 'warning' : 'danger'"
              />
              <div v-if="row.sourceEnabled === false" class="cell-sub text-warn">网站已停用</div>
            </td>
            <td>
              <div>{{ initLabel(row) }}</div>
              <div class="cell-sub">{{ row.historyRows || 0 }} 个交易日 · 至 {{ row.lastHistoryDate || '—' }}</div>
            </td>
            <td>{{ row.lastSnapshotAt || '—' }}</td>
            <td class="ops-cell">
              <button
                class="btn btn-default btn-sm"
                :disabled="row.sourceEnabled === false"
                @click="store.verifyCollect(row.id)"
              >
                校验
              </button>
              <button
                class="btn btn-default btn-sm"
                :disabled="row.sourceEnabled === false"
                @click="startBackfill(row)"
              >
                回补
              </button>
              <button
                class="btn btn-default btn-sm"
                :disabled="row.sourceEnabled === false"
                @click="store.toggleCollect(row.id)"
              >
                {{ row.status === '启用' ? '停用' : '启用' }}
              </button>
              <button class="btn btn-default btn-sm" @click="openEdit(row)">编辑</button>
              <button class="btn btn-default btn-sm" @click="remove(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!filteredConfigs.length">
            <td colspan="8" class="empty-cell">
              {{ activeSource ? '该网站下没有符合条件的采集配置' : '暂无网站配置' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="showForm" class="modal-mask">
    <div class="modal-panel">
      <div class="modal-head">
        <span>{{ editingId ? '编辑采集配置' : '新增采集配置' }}</span>
        <button class="modal-close" @click="closeForm">×</button>
      </div>

      <div class="modal-body">
        <div class="form-row">
          <label>网站：</label>
          <AppSelect
            v-model="form.source"
            :options="formSourceOptions"
            :disabled="!!editingId"
            style="width: 200px"
            @change="onSourceChange"
          />
          <span class="form-hint">当前仅富宝资讯支持自动解析</span>
        </div>

        <div class="form-row">
          <label>网站物料名称：</label>
          <input v-model="form.keyword" :disabled="!!editingId" placeholder="如 机生铝 / 黄杂铜" />
        </div>

        <div class="form-row">
          <label>省 / 直辖市：</label>
          <AppSelect
            v-model="form.provinceId"
            :options="provinceSelectOptions"
            :disabled="!!editingId"
            searchable
            style="width: 210px"
            @change="onProvinceChange"
          />
          <label>市：</label>
          <AppSelect
            v-model="form.cityId"
            :options="citySelectOptions"
            :disabled="!!editingId || !form.provinceId"
            searchable
            style="width: 190px"
            @change="onCityChange"
          />
          <button
            v-if="!editingId"
            class="btn btn-primary btn-sm"
            :disabled="searching"
            @click="doSearch"
          >
            {{ searching ? '搜索中…' : '搜索富宝产品' }}
          </button>
        </div>

        <div v-if="searchInfo" class="search-info">{{ searchInfo }}</div>

        <div v-if="!editingId && candidates.length" class="candidate-wrap">
          <table class="data-table candidate-table">
            <thead>
              <tr>
                <th></th>
                <th>网站物料全称</th>
                <th>地区</th>
                <th>规格</th>
                <th>含税</th>
                <th>单位</th>
                <th>今日价格</th>
                <th>涨跌</th>
                <th>已绑定</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in candidates"
                :key="item.productId"
                :class="{ 'candidate-selected': item.productId === form.productId }"
                @click="chooseCandidate(item)"
              >
                <td>
                  <input
                    type="radio"
                    name="collectCandidate"
                    :value="item.productId"
                    v-model="form.productId"
                    @change="chooseCandidate(item)"
                  />
                </td>
                <td>
                  {{ item.externalName }}
                  <span v-if="item.matched" class="status-tag status-success">地区匹配</span>
                  <span v-else class="status-tag status-warning">其他地区</span>
                </td>
                <td>{{ item.place || '—' }}</td>
                <td>{{ item.spec || '—' }}</td>
                <td>{{ item.tax || '—' }}</td>
                <td>{{ item.unit || '—' }}</td>
                <td class="price-cell">{{ item.price || '—' }}</td>
                <td>{{ item.change || '—' }}</td>
                <td>
                  <span v-if="item.boundMaterial">
                    {{ item.boundMaterial.code }} {{ item.boundMaterial.name }}
                  </span>
                  <span v-else>—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="form.productId" class="selected-card">
          已选：{{ form.externalName }}
        </div>

        <div class="form-row">
          <label>网站物料：</label>
          <template v-if="editingId">
            <input :value="`${form.materialCode}（自动创建）`" disabled />
          </template>
          <template v-else>
            <span class="form-hint">
              系统将自动创建网站物料：按「{{ form.cityId ? '市' : '省' }}简称 + 物料名称」命名，编码顺延 WBxxxxx；保存后可到「物料计价规则」配置对应的公司系统物料。
            </span>
          </template>
        </div>

        <div class="form-row">
          <label>初始回补天数：</label>
          <input v-model.number="form.historyDays" type="number" min="1" max="365" />
          <span class="form-hint">{{ historyHint }}</span>
        </div>
        <div v-if="editingId" class="form-hint" style="margin: -4px 0 8px 130px">
          当前配置 {{ originalHistoryDays }} 天；调大后保存会自动继续往更早补，不删除已有数据。
        </div>

        <div class="form-row">
          <label>备注：</label>
          <input v-model="form.remark" placeholder="可选" />
        </div>

        <div class="form-row">
          <label>启用：</label>
          <label class="checkbox-item">
            <input v-model="form.enabled" type="checkbox" />
            保存后参与每日同步
          </label>
        </div>

        <div v-if="selectedCandidate && !selectedCandidate.matched" class="warn-box">
          <template v-if="form.cityId">
            所选产品的报价地区为「{{ selectedCandidate.place }}」，与选择的省市不一致，请确认后再保存。
          </template>
          <template v-else>
            未指定市，所选产品报价地区为「{{ selectedCandidate.place }}」，系统将按全省匹配；请确认后再保存。
          </template>
        </div>
      </div>

      <div class="modal-foot">
        <button class="btn btn-default" @click="closeForm">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{
            saving
              ? '保存并启动同步…'
              : (!editingId || historyExpanded ? '保存配置并同步历史数据' : '保存配置')
          }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="accountModalOpen" class="modal-mask" @click.self="closeAccountModal">
    <div class="modal-panel account-modal">
      <div class="modal-head">
        <span>富宝资讯 · 用户账号</span>
        <button class="modal-close" @click="closeAccountModal">×</button>
      </div>

      <div class="modal-body">
        <div class="account-status">
          <span class="account-status-label">当前状态：</span>
          <span v-if="collectToken.valid && autoRenew" class="status-tag status-success">已登录</span>
          <span v-else-if="collectToken.valid" class="status-tag status-success">Token 有效</span>
          <span v-else-if="collectToken.present" class="status-tag status-danger">已过期</span>
          <span v-else class="status-tag status-warning">未登录</span>
          <span v-if="autoRenew" class="form-hint">
            账号 {{ collectToken.autoRenewAccount || '—' }}
          </span>
          <span v-if="collectToken.expiry" class="form-hint">
            有效期 {{ collectToken.expiry }}
            <template v-if="tokenRemaining">（{{ tokenRemaining }}）</template>
          </span>
          <button
            class="btn btn-default btn-sm"
            :disabled="collectToken.loading"
            @click="store.loadCollectToken()"
          >
            刷新状态
          </button>
        </div>

        <div class="form-row">
          <label>用户名 / 手机号：</label>
          <input
            v-model="credentialForm.username"
            placeholder="请输入富宝账号"
            autocomplete="username"
          />
        </div>
        <div class="form-row">
          <label>密码：</label>
          <input
            v-model="credentialForm.password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
            @keyup.enter="saveCredentials"
          />
        </div>

        <div v-if="collectToken.refreshError" class="warn-box">
          {{ collectToken.refreshError }}
        </div>
        <div class="form-hint">
          登录成功后自动获取 AUTH_COOKIE 并保存账号；token 过期后系统会自动用该账号重新登录。
          账号密码使用 Windows DPAPI 加密保存到 cred.dat，仅当前 Windows 账户可解密。
        </div>

        <div v-if="autoRenew" class="account-actions">
          <button
            class="btn btn-default btn-sm"
            :disabled="credentialRefreshing"
            @click="refreshTokenNow"
          >
            {{ credentialRefreshing ? '续期中…' : '立即续期' }}
          </button>
          <button class="btn btn-default btn-sm" @click="removeCredentials">退出账号</button>
        </div>

        <div class="token-manual">
          <button class="link-btn" @click="showTokenForm = !showTokenForm">
            {{ showTokenForm ? '收起手动 Token' : '使用 AUTH_COOKIE 临时登录（备用）' }}
          </button>
          <template v-if="showTokenForm">
            <div class="token-row">
              <input
                v-model="tokenInput"
                type="password"
                placeholder="粘贴 AUTH_COOKIE（形如 xxxxx|2026-11-01 10:00:00）"
                autocomplete="off"
              />
              <button
                class="btn btn-primary btn-sm"
                :disabled="tokenSaving || !tokenInput.trim()"
                @click="saveToken"
              >
                {{ tokenSaving ? '保存中…' : '保存 Token' }}
              </button>
            </div>
            <div class="form-hint">
              当前：{{ collectToken.masked || '未录入' }} · 保存到
              {{ collectToken.filePath || 'auth_token.txt' }}
              <span v-if="collectToken.source === 'env'"> · 正在使用环境变量 F139_TOKEN</span>
            </div>
          </template>
        </div>
      </div>

      <div class="modal-foot">
        <button class="btn btn-default" @click="closeAccountModal">取消</button>
        <button
          class="btn btn-primary"
          :disabled="credentialSaving || !credentialForm.username.trim() || !credentialForm.password"
          @click="saveCredentials"
        >
          {{ credentialSaving ? '登录中…' : '登录并启用自动续期' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cell-sub {
  margin-top: 2px;
  color: #8aa0b6;
  font-size: 12px;
}

.text-warn {
  color: #e65100;
}

.ops-cell {
  white-space: nowrap;
}

.search-info {
  margin: 6px 0 10px;
  font-size: 12px;
  color: #1565c0;
}

.candidate-wrap {
  max-height: 300px;
  overflow: auto;
  border: 1px solid #e3edf7;
  border-radius: 6px;
  margin-bottom: 12px;
}

.candidate-table th {
  position: sticky;
  top: 0;
  z-index: 1;
}

.candidate-table tbody tr {
  cursor: pointer;
}

.candidate-selected td {
  background: #e3f2fd !important;
}

.selected-card {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f0f7ff;
  border: 1px solid #cfe4fb;
  border-radius: 4px;
  font-size: 13px;
  color: #1565c0;
}

.warn-box {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fff3e0;
  border: 1px solid #ffe0b2;
  border-radius: 4px;
  font-size: 12px;
  color: #e65100;
}

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
  max-width: 1080px;
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
  width: 110px;
  flex: 0 0 110px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e8f0f8;
}

.source-account {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid #e3edf7;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

.source-account:hover {
  border-color: #1e88e5;
}

.source-account-title {
  color: #7b8ea6;
  font-size: 12px;
}

.source-account-name {
  color: #1a3a5c;
  font-size: 13px;
  font-weight: 600;
}

.source-account-token {
  flex: 1;
  min-width: 180px;
}

.source-account-link {
  margin-left: auto;
  color: #1e88e5;
  font-size: 12px;
}

.account-modal {
  width: 620px;
  max-width: calc(100vw - 40px);
}

.account-status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  margin-bottom: 12px;
  border-bottom: 1px dashed #d6e6f6;
}

.account-status-label {
  color: #4a5f75;
  font-size: 13px;
}

.account-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.token-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.token-row input {
  flex: 1;
  min-width: 240px;
}

.token-manual {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #d6e6f6;
}

.link-btn {
  padding: 0;
  border: none;
  background: none;
  color: #1e88e5;
  font-size: 12px;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

.source-card {
  border: 1px solid #e3edf7;
  border-radius: 8px;
  padding: 14px 16px;
  background: #fafcff;
}

.source-panel {
  margin-bottom: 12px;
}

.source-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.source-name {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 15px;
  font-weight: 600;
  color: #1a3a5c;
}

.source-stats {
  margin-top: 6px;
  font-size: 12px;
  color: #7b8ea6;
}

.source-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: #7b8ea6;
}

.source-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.switch-wrap {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.switch-wrap input {
  display: none;
}

.switch-track {
  position: relative;
  display: inline-block;
  width: 42px;
  height: 22px;
  border-radius: 12px;
  background: #cfd8e3;
  transition: background 0.2s;
}

.switch-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  transition: left 0.2s;
}

.switch-wrap input:checked + .switch-track {
  background: #2e7d32;
}

.switch-wrap input:checked + .switch-track .switch-knob {
  left: 22px;
}

.switch-wrap input:disabled + .switch-track {
  opacity: 0.45;
  cursor: not-allowed;
}

.switch-wrap.small .switch-track {
  width: 34px;
  height: 18px;
  border-radius: 10px;
}

.switch-wrap.small .switch-knob {
  width: 14px;
  height: 14px;
}

.switch-wrap.small input:checked + .switch-track .switch-knob {
  left: 18px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}


</style>
