<script setup>
import { computed, ref } from 'vue'
import StatusTag from '../components/StatusTag.vue'
import { useMarketStore } from '../stores/market'

const store = useMarketStore()
const showLogs = ref(false)
const detailBatch = ref(null)

const executionLogs = computed(() =>
  store.state.logs.filter((log) => log.type === '计价执行')
)
const batchResults = computed(() =>
  detailBatch.value
    ? store.state.results.filter((row) => row.batchId === detailBatch.value.id)
    : []
)

function openBatch(batch) {
  detailBatch.value = batch
}
</script>

<template>
  <div class="breadcrumb">首页 / 计价执行 / <span>自动计价任务</span></div>
  <div class="page-title">自动计价任务管理</div>

  <div class="card">
    <div class="card-title">⏱ 定时任务调度</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>任务名称</th>
            <th>执行周期</th>
            <th>任务状态</th>
            <th>上次执行时间</th>
            <th>下次执行时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="schedule in store.state.schedules" :key="schedule.id">
            <td>{{ schedule.name }}</td>
            <td>{{ schedule.cycle }}</td>
            <td><StatusTag :text="schedule.status" type="success" /></td>
            <td>{{ schedule.lastRun }}</td>
            <td>{{ schedule.nextRun }}</td>
            <td>
              <button class="btn btn-primary btn-sm" @click="store.runSchedule(schedule.id)">立即执行</button>
              <button class="btn btn-default btn-sm" @click="showLogs = !showLogs">执行日志</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-title">📊 最近执行批次</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>批次编号</th>
            <th>执行时间</th>
            <th>计算物料数</th>
            <th>成功数</th>
            <th>失败数</th>
            <th>执行状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="batch in store.state.batches" :key="batch.id">
            <td>{{ batch.id }}</td>
            <td>{{ batch.runAt }}</td>
            <td>{{ batch.total }}</td>
            <td>{{ batch.success }}</td>
            <td>{{ batch.failed }}</td>
            <td>
              <StatusTag
                :text="batch.status"
                :type="batch.status === '成功' ? 'success' : 'warning'"
              />
            </td>
            <td><button class="btn btn-default btn-sm" @click="openBatch(batch)">查看明细</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="showLogs" class="card">
    <div class="card-title">📝 计价执行日志（{{ executionLogs.length }} 条）</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>操作人</th>
            <th>内容</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(log, index) in executionLogs" :key="index">
            <td>{{ log.time }}</td>
            <td>{{ log.operator }}</td>
            <td>{{ log.content }}</td>
          </tr>
          <tr v-if="!executionLogs.length">
            <td colspan="3" class="empty-cell">暂无计价执行日志</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="detailBatch" class="card">
    <div class="card-title">
      📦 批次明细：{{ detailBatch.id }}（{{ batchResults.length }} 条）
    </div>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>网站物料</th>
            <th>系统物料编码</th>
            <th>系统物料名称</th>
            <th>模板</th>
            <th>统计周期</th>
            <th>周期均价</th>
            <th>固定调整值</th>
            <th>系数</th>
            <th>计算售价</th>
            <th>复核状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in batchResults" :key="row.id">
            <td>{{ row.sourceMaterialCode || '—' }}</td>
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
            <td>
              <StatusTag
                :text="row.reviewStatus"
                :type="row.reviewStatus === '已复核' ? 'success' : row.reviewStatus === '已驳回' ? 'warning' : 'info'"
              />
            </td>
          </tr>
          <tr v-if="!batchResults.length">
            <td colspan="10" class="empty-cell">该批次没有计价结果</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="form-actions">
      <button class="btn btn-default btn-sm" @click="detailBatch = null">关闭</button>
    </div>
  </div>
</template>
