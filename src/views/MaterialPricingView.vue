<script setup>
import { computed, reactive, ref, watch } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const editModel = ref(null)
const createModel = ref(null)
const newMaterialName = ref('')
const groupCoefficient = reactive({})
const savingGroup = ref(null)

const groups = computed(() => store.state.pricingRules.groups || [])
const systemMaterials = computed(() =>
  store.state.materials.filter((item) => item.materialType === '系统')
)
const templates = computed(() => store.state.templates)

watch(
  groups,
  (list) => {
    list.forEach((group) => {
      if (groupCoefficient[group.sourceConfigId] !== undefined) return
      const first = group.rules.find((rule) => rule.status === '生效') || group.rules[0]
      groupCoefficient[group.sourceConfigId] = first ? Number(first.coefficient ?? 1) : 1.03
    })
  },
  { immediate: true }
)

function openEdit(group, rule) {
  editModel.value = {
    ...rule,
    sourceConfigId: group.sourceConfigId,
    sourceMaterialCode: group.sourceMaterialCode,
    sourceMaterialName: group.sourceMaterialName,
    offset: rule.offset ?? 0,
    coefficient: rule.coefficient ?? 1
  }
}

async function saveEdit() {
  if (!editModel.value) return
  const ok = await store.updatePricingRule(editModel.value.id, {
    templateCode: editModel.value.templateCode,
    period: editModel.value.period || '周',
    offset: Number(editModel.value.offset) || 0,
    coefficient: Number(editModel.value.coefficient) || 1,
    status: editModel.value.status
  })
  if (ok) editModel.value = null
}

async function toggleRule(group, rule) {
  await store.updatePricingRule(rule.id, {
    templateCode: rule.templateCode,
    period: rule.period || '周',
    offset: Number(rule.offset) || 0,
    coefficient: Number(rule.coefficient ?? 1),
    status: rule.status === '生效' ? '停用' : '生效'
  })
}

async function applyCoefficient(group) {
  const value = Number(groupCoefficient[group.sourceConfigId])
  if (!Number.isFinite(value) || value <= 0) {
    store.notify('调价系数需大于 0')
    return
  }
  savingGroup.value = group.sourceConfigId
  await store.applyGroupCoefficient(group.sourceConfigId, value)
  savingGroup.value = null
}

function openCreate(group) {
  const used = new Set(group.rules.map((rule) => rule.materialCode))
  const options = systemMaterials.value.filter((item) => !used.has(item.code))
  createModel.value = {
    sourceConfigId: group.sourceConfigId,
    sourceMaterialCode: group.sourceMaterialCode,
    sourceMaterialName: group.sourceMaterialName,
    materialCode: options[0]?.code || '',
    templateCode: 'TPL02',
    period: '周',
    offset: 0,
    coefficient: Number(groupCoefficient[group.sourceConfigId] ?? 1.03),
    options
  }
}

async function createSystemMaterial() {
  const name = (newMaterialName.value || '').trim()
  if (!name) {
    store.notify('请输入系统物料名称')
    return
  }
  const item = await store.createMaterial({ name, materialType: '系统' })
  if (!item) return
  if (createModel.value && !createModel.value.options.some((entry) => entry.code === item.code)) {
    createModel.value.options.push(item)
  }
  if (createModel.value) createModel.value.materialCode = item.code
  newMaterialName.value = ''
}

async function saveCreate() {
  if (!createModel.value) return
  if (!createModel.value.materialCode) {
    store.notify('请选择公司系统物料')
    return
  }
  const item = await store.createPricingRule({
    sourceConfigId: createModel.value.sourceConfigId,
    materialCode: createModel.value.materialCode,
    templateCode: createModel.value.templateCode,
    period: createModel.value.period,
    offset: Number(createModel.value.offset) || 0,
    coefficient: Number(createModel.value.coefficient) || 1
  })
  if (item) createModel.value = null
}
</script>

<template>
  <div class="breadcrumb">首页 / 定价配置 / <span>物料计价规则</span></div>
  <div class="page-title">物料计价规则维护</div>

  <div class="card">
    <div class="tip-box">
      💡 说明：一个网站物料可对应多个公司系统物料。计算售价 =（上一完整周均价 + 固定调整值）×
      调价系数，结果保留两位小数。固定调整值为 0 表示不增不减；统计周期为周一到周日的完整周，
      其中周一至周五有报价、周六日无更新，只用周一至周五的报价计算周均价。
    </div>

    <div v-if="!groups.length" class="empty-cell">暂无网站物料采集配置，请先到「网站物料采集配置」新增。</div>

    <div v-for="group in groups" :key="group.sourceConfigId" class="pricing-group">
      <div class="pricing-group-head">
        <div class="pricing-group-title">
          <strong>{{ group.sourceMaterialCode || '未绑定' }}</strong>
          <span>{{ group.sourceMaterialName || group.keyword }}</span>
          <StatusTag
            :text="group.status"
            :type="group.status === '启用' ? 'success' : 'warning'"
          />
        </div>
        <div class="pricing-group-meta">
          {{ group.source }} · {{ group.region }}
          <span class="form-hint">{{ group.externalName }}</span>
        </div>
      </div>

      <div class="pricing-week">
        <span>
          统计周期 {{ group.periodStart }} ~ {{ group.periodEnd }}（完整周）
        </span>
        <span>有效报价 {{ group.quoteDays || 0 }} 天（周一至周五）</span>
        <span class="week-avg">
          周均价 <strong>{{ store.formatPrice2(group.periodAvg) }}</strong> 元/吨
        </span>
      </div>

      <div class="coefficient-bar">
        <label>统一调价系数：</label>
        <input
          v-model.number="groupCoefficient[group.sourceConfigId]"
          type="number"
          step="0.01"
          min="0"
          style="width: 100px"
        />
        <button
          class="btn btn-default btn-sm"
          :disabled="!group.rules.length || savingGroup === group.sourceConfigId"
          @click="applyCoefficient(group)"
        >
          应用到本组 {{ group.rules.length }} 个系统物料
        </button>
        <button class="btn btn-primary btn-sm action-right" @click="openCreate(group)">
          新增系统物料
        </button>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>系统物料编码</th>
              <th>系统物料名称</th>
              <th>绑定模板</th>
              <th>固定调整值</th>
              <th>调价系数</th>
              <th>计算售价（预览）</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in group.rules" :key="rule.id">
              <td>{{ rule.materialCode }}</td>
              <td>{{ rule.materialName }}</td>
              <td>{{ rule.templateCode }}</td>
              <td :class="rule.offset > 0 ? 'text-up' : rule.offset < 0 ? 'text-down' : ''">
                {{ store.formatAdjust(rule.offset) }}
              </td>
              <td>{{ rule.coefficient === null ? '—' : Number(rule.coefficient).toFixed(2) }}</td>
              <td class="price-cell">{{ store.formatPrice2(rule.previewPrice) }}</td>
              <td>
                <StatusTag
                  :text="rule.status"
                  :type="rule.status === '生效' ? 'success' : 'warning'"
                />
              </td>
              <td>
                <button class="btn btn-default btn-sm" @click="openEdit(group, rule)">编辑</button>
                <button class="btn btn-default btn-sm" @click="toggleRule(group, rule)">
                  {{ rule.status === '生效' ? '停用' : '启用' }}
                </button>
              </td>
            </tr>
            <tr v-if="!group.rules.length">
              <td colspan="8" class="empty-cell">
                尚未配置公司系统物料，点击右上角「新增系统物料」建立对应关系。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="groups.length" class="tip-box" style="margin-top: 12px">
      计价执行时会按上一完整周（周一至周日）的周一至周五报价计算周均价，并为每个系统物料生成一条计价结果。
    </div>
  </div>

  <div v-if="createModel" class="modal-demo">
    <h4>📋 新增系统物料规则（{{ createModel.sourceMaterialCode }} {{ createModel.sourceMaterialName }}）</h4>
    <div v-if="!createModel.options.length" class="form-hint" style="margin-bottom: 10px">
      暂无可选的系统物料，可在下方直接新建（编码自动顺延 XTxxxxx）。
    </div>
    <div class="form-row">
      <label>公司系统物料：</label>
      <select v-model="createModel.materialCode">
        <option v-for="item in createModel.options" :key="item.code" :value="item.code">
          {{ item.code }} {{ item.name }}
        </option>
      </select>
    </div>
    <div class="form-row">
      <label>新建系统物料：</label>
      <input v-model="newMaterialName" placeholder="如：黄杂铜" style="width: 140px" />
      <button class="btn btn-default btn-sm" @click="createSystemMaterial">新建并选中</button>
    </div>
    <div class="form-row">
      <label>绑定模板：</label>
      <select v-model="createModel.templateCode">
        <option v-for="template in templates" :key="template.code" :value="template.code">
          {{ template.code }} {{ template.name }}
        </option>
      </select>
    </div>
    <div class="form-row">
      <label>固定调整值：</label>
      <input v-model.number="createModel.offset" type="number" style="width: 120px" />
      <span class="form-hint">（0 = 不增不减，负数扣减）</span>
    </div>
    <div class="form-row">
      <label>调价系数：</label>
      <input v-model.number="createModel.coefficient" type="number" step="0.01" style="width: 120px" />
    </div>
    <div class="form-actions">
      <button class="btn btn-default btn-sm" @click="createModel = null">取消</button>
      <button class="btn btn-primary btn-sm" @click="saveCreate">保存规则</button>
    </div>
  </div>

  <div v-if="editModel" class="modal-demo">
    <h4>📋 编辑计价规则（{{ editModel.materialCode }} {{ editModel.materialName }}）</h4>
    <div class="form-row">
      <label>网站物料：</label>
      <input :value="`${editModel.sourceMaterialCode} ${editModel.sourceMaterialName}`" disabled />
    </div>
    <div class="form-row">
      <label>绑定模板：</label>
      <select v-model="editModel.templateCode">
        <option v-for="template in templates" :key="template.code" :value="template.code">
          {{ template.code }} {{ template.name }}
        </option>
      </select>
    </div>
    <div class="form-row">
      <label>固定调整值：</label>
      <input v-model.number="editModel.offset" type="number" style="width: 120px" />
      <span class="form-hint">（0 = 不增不减，负数扣减）</span>
    </div>
    <div class="form-row">
      <label>调价系数：</label>
      <input v-model.number="editModel.coefficient" type="number" step="0.01" style="width: 120px" />
    </div>
    <div class="form-row">
      <label>规则状态：</label>
      <select v-model="editModel.status">
        <option>生效</option>
        <option>停用</option>
      </select>
    </div>
    <div class="form-actions">
      <button class="btn btn-default btn-sm" @click="editModel = null">取消</button>
      <button class="btn btn-primary btn-sm" @click="saveEdit">保存规则</button>
    </div>
  </div>
</template>

<style scoped>
.pricing-group {
  border: 1px solid #e5e8ef;
  border-radius: 8px;
  padding: 14px 16px 4px;
  margin-bottom: 16px;
  background: #fff;
}

.pricing-group-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
}

.pricing-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
}

.pricing-group-meta {
  color: #6b7280;
  font-size: 12px;
}

.pricing-week {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin: 10px 0;
  padding: 8px 12px;
  background: #f7f9fc;
  border-radius: 6px;
  color: #4b5563;
  font-size: 13px;
}

.pricing-week .week-avg strong {
  color: #1f2937;
  font-size: 15px;
}

.coefficient-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.coefficient-bar .action-right {
  margin-left: auto;
}
</style>
