<script setup>
import { onMounted } from 'vue'
import { useMarketStore } from './stores/market'

const store = useMarketStore()

onMounted(() => {
  if (!store.state.loaded) {
    store.loadAll()
  }
})

const menuGroups = [
  {
    title: '行情管理',
    items: [
      { name: 'market', label: '行情数据台账' },
      { name: 'mapping', label: '物料信息映射表' },
      { name: 'collect', label: '网站物料采集配置' }
    ]
  },
  {
    title: '定价配置',
    items: [
      { name: 'templates', label: '定价规则模板' },
      { name: 'params', label: '物料计价规则' }
    ]
  },
  {
    title: '计价执行',
    items: [
      { name: 'tasks', label: '自动计价任务' },
      { name: 'results', label: '计价结果管理' }
    ]
  },
  {
    title: '数据看板',
    items: [
      { name: 'dashboard', label: '行情价格看板' },
      { name: 'logs', label: '操作日志追溯' }
    ]
  }
]
</script>

<template>
  <div class="top-header">
    <div class="logo">📊 商品行情采集与自动定价系统</div>
    <div class="user-info">
      <span
        class="api-badge"
        :class="store.state.apiOnline ? 'online' : 'offline'"
        :title="store.state.error || 'SQLite API 已连接'"
      >
        {{ store.state.loading ? '连接中' : store.state.apiOnline ? 'SQLite API' : '本地演示数据' }}
      </span>
      管理员 | 行情计价模块
    </div>
  </div>

  <div class="layout">
    <aside class="sidebar">
      <template v-for="group in menuGroups" :key="group.title">
        <div class="menu-group-title">{{ group.title }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.name"
          :to="{ name: item.name }"
          class="menu-item"
        >
          {{ item.label }}
        </router-link>
      </template>
      <div class="sidebar-note">Vue 3 + Vite</div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
  </div>

  <transition name="toast">
    <div v-if="store.state.toast.visible" class="app-toast">
      {{ store.state.toast.message }}
    </div>
  </transition>
</template>
