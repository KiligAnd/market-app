<script setup>
import { computed, ref } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const typeFilter = ref('全部')
const operatorFilter = ref('')
const dateFilter = ref('')

const typeClass = {
  行情采集: 'info',
  参数修改: 'warning',
  计价执行: 'success',
  物料映射变更: 'info',
  复核: 'success',
  报表导出: 'info'
}

const filteredLogs = computed(() =>
  store.state.logs.filter((log) => {
    if (typeFilter.value !== '全部' && log.type !== typeFilter.value) return false
    if (operatorFilter.value && !log.operator.includes(operatorFilter.value)) return false
    if (dateFilter.value && !log.time.startsWith(dateFilter.value)) return false
    return true
  })
)
</script>

<template>
  <div class="breadcrumb">首页 / 数据看板 / <span>操作日志追溯</span></div>
  <div class="page-title">操作日志追溯</div>

  <div class="card">
    <div class="filter-bar">
      <label>操作类型：</label>
      <select v-model="typeFilter">
        <option>全部</option>
        <option>行情采集</option>
        <option>物料映射变更</option>
        <option>参数修改</option>
        <option>计价执行</option>
        <option>复核</option>
        <option>报表导出</option>
      </select>

      <label>操作人：</label>
      <input v-model="operatorFilter" placeholder="输入操作人" />
      <label>日期：</label>
      <input v-model="dateFilter" type="date" />
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>日志时间</th>
            <th>操作类型</th>
            <th>操作人</th>
            <th>操作内容</th>
            <th>IP地址</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(log, index) in filteredLogs" :key="`${log.time}-${index}`">
            <td>{{ log.time }}</td>
            <td><StatusTag :text="log.type" :type="typeClass[log.type] || 'info'" /></td>
            <td>{{ log.operator }}</td>
            <td>{{ log.content }}</td>
            <td>{{ log.ip }}</td>
          </tr>
          <tr v-if="!filteredLogs.length">
            <td colspan="5" class="empty-cell">没有符合条件的操作日志</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-title">🔌 今日接口调用审计</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>调用时间</th>
            <th>模式</th>
            <th>用途</th>
            <th>接口</th>
            <th>方法</th>
            <th>状态码</th>
            <th>耗时</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(call, index) in store.state.apiCallLogs" :key="`${call.time}-${index}`">
            <td>{{ call.time }}</td>
            <td>{{ call.mode }}</td>
            <td>{{ call.purpose }}</td>
            <td class="endpoint-cell">{{ call.endpoint }}</td>
            <td>{{ call.method }}</td>
            <td><StatusTag :text="String(call.status)" type="success" /></td>
            <td>{{ call.elapsed }} ms</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="chart-note">
      今日共 {{ store.state.syncStatus.callsToday }} 次调用；初始化阶段 20~45 秒随机间隔，日常 5~15 秒，同一天重复运行直接跳过。
    </div>
  </div>
</template>
