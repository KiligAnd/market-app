<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()

const keyword = ref('')
const sourceFilter = ref('全部')
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const showImport = ref(false)
const importing = ref(false)
const importText = ref('')
const importErrors = ref([])
const websiteMaterialKeyword = ref('')
const websiteMaterialOpen = ref(false)
const wmSelectRef = ref(null)
const wmSearchRef = ref(null)
const systemMaterialKeyword = ref('')
const systemMaterialOpen = ref(false)
const smSelectRef = ref(null)
const smSearchRef = ref(null)

const form = reactive({
  sourceCode: '',
  sourceConfigId: '',
  materialCode: '',
  offset: 0,
  coefficient: 1.03
})

const editForm = reactive({
  id: null,
  materialCode: '',
  materialName: '',
  configLabel: '',
  offset: 0,
  coefficient: 1.03,
  status: '生效'
})

const filteredRows = computed(() =>
  store.state.mappings.filter((row) => {
    if (sourceFilter.value !== '全部' && row.source !== sourceFilter.value) return false
    if (!keyword.value) return true
    const text = [
      row.materialCode, row.materialName, row.keyword, row.externalName,
      row.productId, row.provinceName, row.cityName
    ].join(' ').toLowerCase()
    return text.includes(keyword.value.toLowerCase())
  })
)

// 可选的网站物料采集配置（未删除）
const configOptions = computed(() =>
  store.state.collectConfigs
    .filter((item) => item.status !== '已删除')
    .map((item) => ({
      id: item.id,
      sourceCode: item.sourceCode,
      source: item.source,
      materialCode: item.materialCode || '',
      materialName: item.materialName || '',
      keyword: item.keyword || '',
      externalName: item.externalName || '',
      remark: item.remark || '',
      provinceName: item.provinceName || '',
      cityName: item.cityName || '',
      productId: item.productId || '',
      status: item.status,
      label: `${item.materialCode || '未绑定'} ${item.materialName || item.keyword}`
    }))
)

function websiteMaterialNote(item) {
  return (item.remark || item.externalName || '').trim()
}

// 先按网站分组，再按网站过滤网站物料
const sourceOptions = computed(() => {
  const map = new Map()
  configOptions.value.forEach((item) => {
    if (!item.sourceCode) return
    if (!map.has(item.sourceCode)) {
      map.set(item.sourceCode, {
        code: item.sourceCode,
        name: item.source,
        count: 0
      })
    }
    map.get(item.sourceCode).count += 1
  })
  return [...map.values()]
})

const websiteMaterialOptions = computed(() =>
  configOptions.value.filter((item) => item.sourceCode === form.sourceCode)
)

const filteredWebsiteMaterials = computed(() => {
  const keyword = websiteMaterialKeyword.value.trim().toLowerCase()
  if (!keyword) return websiteMaterialOptions.value
  return websiteMaterialOptions.value.filter((item) =>
    `${item.materialCode} ${item.materialName} ${item.keyword} ${item.externalName} ${item.productId}`
      .toLowerCase()
      .includes(keyword)
  )
})

const selectedSourceOption = computed(() =>
  sourceOptions.value.find((item) => item.code === form.sourceCode) || null
)

const selectedWebsiteMaterial = computed(() =>
  websiteMaterialOptions.value.find((item) => Number(item.id) === Number(form.sourceConfigId)) || null
)

const selectedWebsiteMaterialLabel = computed(() => {
  const item = selectedWebsiteMaterial.value
  if (!item) return ''
  const note = websiteMaterialNote(item)
  return `${item.materialCode || '未绑定'} ${item.materialName || item.keyword}${note ? `（${note}）` : ''}`
})

const selectedSystemMaterial = computed(() =>
  store.state.materials.find((item) => item.code === form.materialCode) || null
)

const selectedSystemMaterialLabel = computed(() => {
  const item = selectedSystemMaterial.value
  return item ? `${item.code} ${item.name}` : ''
})

const filteredSystemMaterials = computed(() => {
  const keyword = systemMaterialKeyword.value.trim().toLowerCase()
  if (!keyword) return materialOptions.value
  return materialOptions.value.filter((item) =>
    `${item.code} ${item.name}`.toLowerCase().includes(keyword)
  )
})

function chooseSource(code) {
  form.sourceCode = code
  websiteMaterialKeyword.value = ''
  websiteMaterialOpen.value = false
  systemMaterialKeyword.value = ''
  systemMaterialOpen.value = false
  form.sourceConfigId = ''
  form.materialCode = ''
}

function toggleWebsiteMaterialDropdown() {
  if (!form.sourceCode) return
  if (websiteMaterialOpen.value) {
    websiteMaterialOpen.value = false
    return
  }
  systemMaterialOpen.value = false
  websiteMaterialKeyword.value = ''
  websiteMaterialOpen.value = true
  nextTick(() => wmSearchRef.value?.focus())
}

function chooseWebsiteMaterial(item) {
  form.sourceConfigId = item.id
  form.materialCode = ''
  websiteMaterialOpen.value = false
  websiteMaterialKeyword.value = ''
  systemMaterialOpen.value = false
}

function toggleSystemMaterialDropdown() {
  if (!materialOptions.value.length) return
  if (systemMaterialOpen.value) {
    systemMaterialOpen.value = false
    return
  }
  websiteMaterialOpen.value = false
  systemMaterialKeyword.value = ''
  systemMaterialOpen.value = true
  nextTick(() => smSearchRef.value?.focus())
}

function chooseSystemMaterial(code) {
  form.materialCode = code
  systemMaterialOpen.value = false
  systemMaterialKeyword.value = ''
}

function handleDocumentClick(event) {
  if (websiteMaterialOpen.value && wmSelectRef.value && !wmSelectRef.value.contains(event.target)) {
    websiteMaterialOpen.value = false
  }
  if (systemMaterialOpen.value && smSelectRef.value && !smSelectRef.value.contains(event.target)) {
    systemMaterialOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleDocumentClick))
onUnmounted(() => document.removeEventListener('click', handleDocumentClick))

// 系统物料（XT），排除当前配置已映射的
const materialOptions = computed(() => {
  if (!form.sourceConfigId) return []
  const used = new Set(
    store.state.mappings
      .filter((row) => row.sourceConfigId === Number(form.sourceConfigId))
      .map((row) => row.materialCode)
  )
  return store.state.materials.filter(
    (item) => item.materialType === '系统' && !used.has(item.code)
  )
})

function configLabel(row) {
  return `${row.source} · ${row.keyword} · ${row.provinceName}${row.cityName}`
}

function openCreate() {
  editingId.value = null
  websiteMaterialKeyword.value = ''
  websiteMaterialOpen.value = false
  systemMaterialKeyword.value = ''
  systemMaterialOpen.value = false
  const preferred = sourceFilter.value !== '全部'
    ? sourceOptions.value.find((item) => item.name === sourceFilter.value)
    : null
  const sourceCode = preferred?.code || sourceOptions.value[0]?.code || ''
  Object.assign(form, {
    sourceCode,
    sourceConfigId: '',
    materialCode: '',
    offset: 0,
    coefficient: 1.03
  })
  showForm.value = true
}

async function save() {
  if (!form.sourceCode) {
    store.notify('请选择网站')
    return
  }
  if (!selectedWebsiteMaterial.value) {
    store.notify('请选择该网站下的网站物料')
    return
  }
  if (!form.materialCode) {
    store.notify('请选择公司系统物料（XT）')
    return
  }
  saving.value = true
  const item = await store.saveMapping(null, {
    sourceConfigId: Number(form.sourceConfigId),
    materialCode: form.materialCode,
    offset: Number(form.offset) || 0,
    coefficient: Number(form.coefficient) || 1
  })
  saving.value = false
  if (item) showForm.value = false
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    id: row.id,
    materialCode: row.materialCode,
    materialName: row.materialName,
    configLabel: configLabel(row),
    offset: row.offset ?? 0,
    coefficient: row.coefficient ?? 1,
    status: row.status
  })
  showForm.value = true
}

async function saveEdit() {
  if (!editForm.id) return
  saving.value = true
  const item = await store.saveMapping(editForm.id, {
    offset: Number(editForm.offset) || 0,
    coefficient: Number(editForm.coefficient) || 1,
    status: editForm.status
  })
  saving.value = false
  if (item) {
    showForm.value = false
    editingId.value = null
  }
}

function openImport() {
  importText.value = ''
  importErrors.value = []
  showImport.value = true
}

async function doImport() {
  if (!importText.value.trim()) {
    store.notify('请粘贴要导入的映射数据')
    return
  }
  importing.value = true
  const data = await store.importMappings(importText.value)
  importing.value = false
  if (!data) return
  importErrors.value = data.errors || []
  if (!importErrors.value.length) {
    showImport.value = false
  }
}
</script>

<template>
  <div class="breadcrumb">首页 / 行情管理 / <span>物料信息映射表</span></div>
  <div class="page-title">物料信息映射表</div>

  <div class="card">
    <div class="tip-box">
      💡 说明：本表维护「公司系统物料 ↔ 网站爬虫物料」的对照关系，一行 = 一个系统物料对应一个爬虫采集物料，
      同时携带计价参数（固定调整值 / 调价系数）。系统物料清单当前手工维护（XT 编码），后续对接 BIP
      物料接口后将自动同步。此处「停用」仅停止该物料计价，不影响行情采集（采集开关在「网站物料采集配置」）。
    </div>

    <div class="filter-bar">
      <label>关键词：</label>
      <input v-model="keyword" placeholder="系统物料 / 网站物料" />
      <label>网站：</label>
      <select v-model="sourceFilter">
        <option>全部</option>
        <option v-for="source in store.state.sources" :key="source.id" :value="source.name">
          {{ source.name }}
        </option>
      </select>
      <button class="btn btn-primary btn-sm action-right" @click="openCreate">
        新增映射关系
      </button>
      <button class="btn btn-default btn-sm" @click="openImport">批量导入</button>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>系统物料编码</th>
            <th>系统物料名称</th>
            <th>网站</th>
            <th>网站物料名称</th>
            <th>省 / 市</th>
            <th>规格 / 含税</th>
            <th>固定调整值</th>
            <th>调价系数</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredRows" :key="row.id">
            <td>{{ row.materialCode }}</td>
            <td>{{ row.materialName }}</td>
            <td>{{ row.source }}</td>
            <td>
              {{ row.keyword }}
              <div class="cell-sub">{{ row.externalName }}</div>
            </td>
            <td>{{ row.provinceName }} / {{ row.cityName }}</td>
            <td>
              {{ row.spec || '—' }}
              <div class="cell-sub">{{ row.tax || '—' }} · {{ row.unit }}</div>
            </td>
            <td :class="row.offset > 0 ? 'text-up' : row.offset < 0 ? 'text-down' : ''">
              {{ store.formatAdjust(row.offset) }}
            </td>
            <td>{{ row.coefficient === null ? '—' : Number(row.coefficient).toFixed(2) }}</td>
            <td>
              <StatusTag
                :text="row.status"
                :type="row.status === '生效' ? 'success' : 'warning'"
              />
            </td>
            <td>
              <button class="btn btn-default btn-sm" @click="openEdit(row)">编辑</button>
              <button class="btn btn-default btn-sm" @click="store.toggleMapping(row.id)">
                {{ row.status === '生效' ? '停用' : '启用' }}
              </button>
            </td>
          </tr>
          <tr v-if="!filteredRows.length">
            <td colspan="10" class="empty-cell">没有符合条件的映射关系</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="showForm && !editingId" class="modal-mask">
    <div class="modal-panel mapping-modal">
      <div class="modal-head">
        <span>新增映射关系</span>
        <button class="modal-close" @click="showForm = false">×</button>
      </div>
      <div class="modal-body mapping-body">
        <div class="mapping-intro">先选网站，再选网站物料，最后绑定公司系统物料。</div>

        <section class="mapping-step">
          <div class="step-head">
            <span class="step-no">1</span>
            <div class="step-title">
              <strong>选择网站</strong>
              <small>确定数据来源</small>
            </div>
          </div>
          <div class="source-choices">
            <button
              v-for="item in sourceOptions"
              :key="item.code"
              type="button"
              class="source-choice"
              :class="{ active: form.sourceCode === item.code }"
              @click="chooseSource(item.code)"
            >
              <span class="source-choice-main">
                <span class="source-choice-name">{{ item.name }}</span>
                <span class="source-choice-count">{{ item.count }} 个网站物料</span>
              </span>
              <span v-if="form.sourceCode === item.code" class="choice-check">✓</span>
            </button>
          </div>
          <div v-if="!sourceOptions.length" class="mapping-empty">
            暂无网站物料采集配置，请先到「网站物料采集配置」新增。
          </div>
        </section>

        <section class="mapping-step">
          <div class="step-head">
            <span class="step-no">2</span>
            <div class="step-title">
              <strong>选择网站物料</strong>
              <small>{{ selectedSourceOption ? selectedSourceOption.name : '请先选择网站' }}</small>
            </div>
          </div>
          <div v-if="form.sourceCode" ref="wmSelectRef" class="wm-select">
            <button
              type="button"
              class="wm-select-trigger"
              :class="{ open: websiteMaterialOpen }"
              @click="toggleWebsiteMaterialDropdown"
            >
              <span v-if="selectedWebsiteMaterialLabel" class="wm-select-value" :title="selectedWebsiteMaterialLabel">
                {{ selectedWebsiteMaterialLabel }}
              </span>
              <span v-else class="wm-select-placeholder">请选择网站物料</span>
              <span class="wm-select-arrow">▾</span>
            </button>

            <div v-if="websiteMaterialOpen" class="wm-select-panel">
              <div class="wm-select-search">
                <input
                  ref="wmSearchRef"
                  v-model="websiteMaterialKeyword"
                  placeholder="搜索网站物料名称 / 编码"
                />
              </div>
              <div class="wm-select-options">
                <button
                  v-for="item in filteredWebsiteMaterials"
                  :key="item.id"
                  type="button"
                  class="wm-option"
                  :class="{ active: Number(form.sourceConfigId) === Number(item.id) }"
                  @click="chooseWebsiteMaterial(item)"
                >
                  <span class="wm-main">
                    <strong>
                      {{ item.materialCode || '未绑定' }} {{ item.materialName || item.keyword }}
                      <template v-if="websiteMaterialNote(item)">（{{ websiteMaterialNote(item) }}）</template>
                    </strong>
                  </span>
                  <span v-if="item.status === '停用'" class="wm-status">停用</span>
                  <span v-if="Number(form.sourceConfigId) === Number(item.id)" class="choice-check">✓</span>
                </button>
                <div v-if="!filteredWebsiteMaterials.length" class="mapping-empty">
                  没有匹配的网站物料
                </div>
              </div>
            </div>
          </div>
          <div v-else class="mapping-empty">请先选择网站</div>
        </section>

        <section class="mapping-step">
          <div class="step-head">
            <span class="step-no">3</span>
            <div class="step-title">
              <strong>公司系统物料与计价参数</strong>
              <small>绑定公司系统物料</small>
            </div>
          </div>
          <div class="mapping-field">
            <label>公司系统物料</label>
            <div ref="smSelectRef" class="wm-select">
              <button
                type="button"
                class="wm-select-trigger"
                :class="{ open: systemMaterialOpen }"
                :disabled="!materialOptions.length"
                @click="toggleSystemMaterialDropdown"
              >
                <span v-if="selectedSystemMaterialLabel" class="wm-select-value" :title="selectedSystemMaterialLabel">
                  {{ selectedSystemMaterialLabel }}
                </span>
                <span v-else class="wm-select-placeholder">
                  {{ materialOptions.length ? '请选择公司系统物料' : '请先选择网站物料' }}
                </span>
                <span class="wm-select-arrow">▾</span>
              </button>

              <div v-if="systemMaterialOpen" class="wm-select-panel">
                <div class="wm-select-search">
                  <input
                    ref="smSearchRef"
                    v-model="systemMaterialKeyword"
                    placeholder="搜索系统物料编码 / 名称"
                  />
                </div>
                <div class="wm-select-options">
                  <button
                    v-for="item in filteredSystemMaterials"
                    :key="item.code"
                    type="button"
                    class="wm-option"
                    :class="{ active: form.materialCode === item.code }"
                    @click="chooseSystemMaterial(item.code)"
                  >
                    <span class="wm-main">
                      <strong>{{ item.code }} {{ item.name }}</strong>
                    </span>
                    <span v-if="form.materialCode === item.code" class="choice-check">✓</span>
                  </button>
                  <div v-if="!filteredSystemMaterials.length" class="mapping-empty">
                    没有匹配的系统物料
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!materialOptions.length && form.sourceConfigId" class="mapping-empty">
              该网站物料已映射全部系统物料，或系统物料清单为空
            </div>
          </div>
          <div class="param-grid">
            <div class="param-field">
              <label>固定调整值</label>
              <input v-model.number="form.offset" type="number" />
              <small>0 = 不增不减，负数扣减</small>
            </div>
            <div class="param-field">
              <label>调价系数</label>
              <input v-model.number="form.coefficient" type="number" step="0.01" />
              <small>默认 1.03</small>
            </div>
          </div>
        </section>

        <div
          v-if="selectedSourceOption && selectedWebsiteMaterial && selectedSystemMaterial"
          class="mapping-preview"
        >
          <div class="preview-route">
            <span>{{ selectedSourceOption.name }}</span>
            <span class="preview-arrow">→</span>
            <span>
              {{ selectedWebsiteMaterial.materialCode || selectedWebsiteMaterial.keyword }}
              {{ selectedWebsiteMaterial.materialName || '' }}
            </span>
            <span class="preview-arrow">→</span>
            <span>{{ selectedSystemMaterial.code }} {{ selectedSystemMaterial.name }}</span>
          </div>
          <div class="preview-formula">
            计价参数：固定调整值 {{ store.formatAdjust(form.offset) }} ·
            调价系数 {{ Number(form.coefficient || 1).toFixed(2) }}
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-default" @click="showForm = false">取消</button>
        <button
          class="btn btn-primary"
          :disabled="saving || !sourceOptions.length || !form.sourceConfigId || !form.materialCode"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="showForm && editingId" class="modal-mask">
    <div class="modal-panel">
      <div class="modal-head">
        <span>编辑映射关系</span>
        <button class="modal-close" @click="showForm = false">×</button>
      </div>
      <div class="modal-body">
        <div class="form-row">
          <label>系统物料：</label>
          <input :value="`${editForm.materialCode} ${editForm.materialName}`" disabled />
        </div>
        <div class="form-row">
          <label>爬虫采集配置：</label>
          <input :value="editForm.configLabel" disabled />
        </div>
        <div class="form-row">
          <label>固定调整值：</label>
          <input v-model.number="editForm.offset" type="number" style="width: 120px" />
          <span class="form-hint">（0 = 不增不减，负数扣减）</span>
        </div>
        <div class="form-row">
          <label>调价系数：</label>
          <input v-model.number="editForm.coefficient" type="number" step="0.01" style="width: 120px" />
        </div>
        <div class="form-row">
          <label>状态：</label>
          <select v-model="editForm.status">
            <option>生效</option>
            <option>停用</option>
          </select>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-default" @click="showForm = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveEdit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="showImport" class="modal-mask">
    <div class="modal-panel">
      <div class="modal-head">
        <span>批量导入映射</span>
        <button class="modal-close" @click="showImport = false">×</button>
      </div>
      <div class="modal-body">
        <div class="import-hint">
          每行一条，逗号或 Tab 分隔：<br />
          系统物料编码, 网站产品编号, 固定调整值, 调价系数<br />
          已存在的「系统物料 + 网站产品编号」组合会被更新参数并置为生效
        </div>
        <textarea
          v-model="importText"
          class="import-textarea"
          rows="10"
          placeholder="XT00001,636,0,1.03&#10;XT00004,1591,-5800,1.18"
        ></textarea>
        <div v-if="importErrors.length" class="import-errors">
          <div v-for="(error, index) in importErrors" :key="index">⚠️ {{ error }}</div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn btn-default" @click="showImport = false">取消</button>
        <button class="btn btn-primary" :disabled="importing" @click="doImport">
          {{ importing ? '导入中…' : '开始导入' }}
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
  max-width: 620px;
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

.modal-body .form-row {
  flex-wrap: wrap;
}

.modal-body .form-row > label {
  width: 130px;
  flex: 0 0 130px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e8f0f8;
}

.import-hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f0f7ff;
  border-radius: 4px;
  font-size: 12px;
  color: #1565c0;
  line-height: 1.6;
}

.import-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-family: Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
}

.import-errors {
  margin-top: 10px;
  max-height: 160px;
  overflow: auto;
  padding: 8px 10px;
  background: #fff3e0;
  border: 1px solid #ffe0b2;
  border-radius: 4px;
  font-size: 12px;
  color: #e65100;
  line-height: 1.6;
}

.mapping-modal {
  max-width: 760px;
}

.mapping-body {
  padding-top: 12px;
}

.mapping-intro {
  margin-bottom: 4px;
  padding: 9px 12px;
  border-left: 3px solid #1e88e5;
  border-radius: 0 4px 4px 0;
  background: #f5faff;
  color: #4a5f75;
  font-size: 12px;
  line-height: 1.6;
}

.mapping-step {
  padding: 14px 0;
  border-bottom: 1px dashed #e3edf7;
}

.mapping-step:last-of-type {
  border-bottom: none;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.step-no {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #1e88e5;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex: 0 0 22px;
}

.step-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-title strong {
  color: #1a3a5c;
  font-size: 14px;
}

.step-title small {
  color: #8aa0b6;
  font-size: 12px;
}

.source-choices {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.source-choice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex: 1;
  min-width: 180px;
  padding: 10px 12px;
  border: 1px solid #dbeaf9;
  border-radius: 8px;
  background: #fff;
  color: #1a3a5c;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.source-choice:hover {
  border-color: #1e88e5;
}

.source-choice.active {
  border-color: #1e88e5;
  background: #eef7ff;
  box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.12);
}

.source-choice-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.source-choice-name {
  font-size: 13px;
  font-weight: 600;
}

.source-choice-count {
  color: #7b8ea6;
  font-size: 12px;
}

.choice-check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #1e88e5;
  color: #fff;
  font-size: 12px;
  flex: 0 0 20px;
}

.wm-select {
  position: relative;
}

.wm-select-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: 1px solid #d0e3f7;
  border-radius: 6px;
  background: #fff;
  color: #1a3a5c;
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.wm-select-trigger:not(:disabled):hover,
.wm-select-trigger.open {
  border-color: #1e88e5;
  box-shadow: 0 0 0 2px rgba(30, 136, 229, 0.12);
}

.wm-select-trigger:disabled {
  border-color: #e3edf7;
  background: #f7f9fc;
  color: #a9bccd;
  cursor: not-allowed;
}

.wm-select-trigger:disabled .wm-select-arrow {
  color: #c2d0de;
}

.wm-select-value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wm-select-placeholder {
  flex: 1;
  color: #9bb0c5;
}

.wm-select-arrow {
  color: #8aa0b6;
  font-size: 11px;
  padding-right: 4px;
  flex: 0 0 auto;
}

.wm-select-panel {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  border: 1px solid #dbeaf9;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 8px 20px rgba(26, 58, 92, 0.14);
}

.wm-select-search {
  padding: 6px;
  border-bottom: 1px solid #eef4fa;
}

.wm-select-search input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-size: 12px;
}

.wm-select-options {
  display: grid;
  gap: 4px;
  max-height: 190px;
  overflow: auto;
  padding: 6px;
}

.wm-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #fff;
  color: #1a3a5c;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.wm-option:hover {
  background: #f5faff;
  border-color: #dbeaf9;
}

.wm-option.active {
  border-color: #1e88e5;
  background: #eef7ff;
}

.wm-main {
  flex: 1;
  min-width: 0;
}

.wm-main strong {
  display: block;
  color: #1a3a5c;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
}

.wm-status {
  padding: 2px 6px;
  border-radius: 3px;
  background: #fff3e0;
  color: #e65100;
  font-size: 11px;
  flex: 0 0 auto;
}

.mapping-empty {
  padding: 12px;
  border: 1px dashed #dbeaf9;
  border-radius: 6px;
  background: #fafcff;
  color: #7b8ea6;
  font-size: 12px;
  text-align: center;
}

.mapping-field label,
.param-field label {
  display: block;
  margin-bottom: 6px;
  color: #4a5f75;
  font-size: 12px;
}

.mapping-field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-size: 13px;
}

.param-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

.param-field input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d0e3f7;
  border-radius: 4px;
  font-size: 13px;
}

.param-field small {
  display: block;
  margin-top: 4px;
  color: #8aa0b6;
  font-size: 11px;
}

.mapping-preview {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid #dbeaf9;
  border-radius: 8px;
  background: #f8fbff;
}

.preview-route {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  color: #1a3a5c;
  font-size: 12px;
}

.preview-arrow {
  color: #8aa0b6;
}

.preview-formula {
  margin-top: 6px;
  color: #7b8ea6;
  font-size: 12px;
}

.mapping-modal {
  max-width: 620px;
}

.mapping-modal .modal-head {
  padding: 12px 16px;
  font-size: 15px;
}

.mapping-modal .modal-body {
  padding: 12px 16px;
}

.mapping-modal .modal-foot {
  padding: 10px 16px;
}

.mapping-body {
  padding-top: 8px;
}

.mapping-intro {
  margin-bottom: 2px;
  padding: 7px 10px;
  font-size: 11px;
}

.mapping-step {
  padding: 10px 0;
}

.step-head {
  gap: 8px;
  margin-bottom: 8px;
}

.step-no {
  width: 20px;
  height: 20px;
  font-size: 11px;
  flex-basis: 20px;
}

.step-title strong {
  font-size: 13px;
}

.step-title small {
  font-size: 11px;
}

.source-choice {
  min-width: 150px;
  padding: 8px 10px;
  border-radius: 6px;
}

.source-choice-name {
  font-size: 12px;
}

.source-choice-count {
  font-size: 11px;
}

.choice-check {
  width: 18px;
  height: 18px;
  font-size: 11px;
  flex-basis: 18px;
}

.wm-select-options {
  max-height: 160px;
}

.wm-status {
  padding: 1px 5px;
  font-size: 10px;
}

.mapping-empty {
  padding: 8px;
  font-size: 11px;
}

.mapping-field label,
.param-field label {
  margin-bottom: 4px;
  font-size: 11px;
}

.param-grid {
  gap: 8px;
  margin-top: 8px;
}

.param-field input {
  padding: 6px 8px;
  font-size: 12px;
}

.param-field small {
  margin-top: 3px;
  font-size: 10px;
}

.mapping-preview {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 6px;
}

.preview-route {
  gap: 4px;
  font-size: 11px;
}

.preview-formula {
  margin-top: 4px;
  font-size: 11px;
}

@media (max-width: 720px) {
  .param-grid {
    grid-template-columns: 1fr;
  }
}
</style>
