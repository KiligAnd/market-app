import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/market' },
  {
    path: '/market',
    name: 'market',
    component: () => import('../views/MarketLedgerView.vue')
  },
  {
    path: '/mapping',
    name: 'mapping',
    component: () => import('../views/MappingView.vue')
  },
  {
    path: '/collect',
    name: 'collect',
    component: () => import('../views/CollectConfigView.vue')
  },
  {
    path: '/templates',
    name: 'templates',
    component: () => import('../views/TemplatesView.vue')
  },
  {
    path: '/params',
    name: 'params',
    component: () => import('../views/MaterialPricingView.vue')
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../views/CalcTasksView.vue')
  },
  {
    path: '/results',
    name: 'results',
    component: () => import('../views/ResultsView.vue')
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue')
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('../views/LogsView.vue')
  },
  { path: '/:pathMatch(.*)*', redirect: '/market' }
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})
