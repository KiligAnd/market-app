<script setup>
import { ref } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const factorOptions = ['固定售价', '多源均价', '统计周期', '固定偏移', '调价系数', '上期价差', '上期售价联动']

const selected = ref(null)
const selectedFactors = ref([])

function selectTemplate(template) {
  selected.value = { ...template, factors: [...template.factors] }
  selectedFactors.value = [...template.factors]
}

async function saveTemplate() {
  if (!selected.value) return
  const ok = await store.updateTemplate(selected.value.id, {
    name: selected.value.name,
    factors: [...selectedFactors.value]
  })
  if (ok) selected.value = null
}
</script>

<template>
  <div class="breadcrumb">首页 / 定价配置 / <span>定价规则模板</span></div>
  <div class="page-title">定价规则模板配置管理</div>

  <div class="card">
    <div class="tip-box">
      💡 说明：模板仅定义计算算式骨架与支持的计算因子，不固定具体参数值。具体参数在「物料计价规则」中按网站物料 → 公司系统物料维护。
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>模板编码</th>
            <th>模板名称</th>
            <th>算式骨架说明</th>
            <th>支持计算因子</th>
            <th>启用状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="template in store.state.templates" :key="template.id">
            <td>{{ template.code }}</td>
            <td>{{ template.name }}</td>
            <td>{{ template.formula }}</td>
            <td>{{ template.factors.join('、') }}</td>
            <td><StatusTag :text="template.enabled ? '启用' : '停用'" :type="template.enabled ? 'success' : 'warning'" /></td>
            <td>
              <button class="btn btn-default btn-sm" @click="selectTemplate(template)">编辑</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selected" class="modal-demo">
      <h4>📋 编辑模板（{{ selected.code }} - {{ selected.name }}）</h4>
      <div class="form-row">
        <label>模板名称：</label>
        <input v-model="selected.name" />
      </div>
      <div class="form-row form-row-top">
        <label>支持因子：</label>
        <div class="checkbox-row">
          <label v-for="factor in factorOptions" :key="factor" class="checkbox-item">
            <input v-model="selectedFactors" type="checkbox" :value="factor" />
            {{ factor }}
          </label>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-default btn-sm" @click="selected = null">取消</button>
        <button class="btn btn-primary btn-sm" @click="saveTemplate">保存</button>
      </div>
    </div>
  </div>
</template>
