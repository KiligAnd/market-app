const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const data = await response.json()
      message = data.detail || message
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(message)
  }
  return response.json()
}

export const api = {
  bootstrap: () => request('/bootstrap'),
  quotes: (params = {}) => {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) {
        search.set(key, value)
      }
    })
    return request(`/quotes?${search.toString()}`)
  },
  toggleMapping: (id) => request(`/mappings/${id}/toggle`, { method: 'POST' }),
  createMapping: (payload) =>
    request('/mappings', { method: 'POST', body: JSON.stringify(payload) }),
  updateMapping: (id, payload) =>
    request(`/mappings/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  importMappings: (text) =>
    request('/mappings/batch-import', {
      method: 'POST',
      body: JSON.stringify({ text })
    }),
  updateParam: (id, payload) =>
    request(`/pricing-params/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  createParam: (payload) =>
    request('/pricing-params', { method: 'POST', body: JSON.stringify(payload) }),

  // 物料计价规则（网站物料 → 公司系统物料）
  createMaterial: (payload) =>
    request('/materials', { method: 'POST', body: JSON.stringify(payload) }),
  pricingRules: () => request('/pricing-rules'),
  createPricingRule: (payload) =>
    request('/pricing-rules', { method: 'POST', body: JSON.stringify(payload) }),
  updatePricingRule: (id, payload) =>
    request(`/pricing-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  applyGroupCoefficient: (sourceConfigId, coefficient) =>
    request(`/pricing-rules/group/${sourceConfigId}/coefficient`, {
      method: 'POST',
      body: JSON.stringify({ coefficient })
    }),

  updateTemplate: (id, payload) =>
    request(`/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  runCollect: () => request('/collect/run', { method: 'POST' }),
  syncStatus: () => request('/sync/status'),
  reviewResult: (id, status) =>
    request(`/results/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ status })
    }),
  batchApprove: () => request('/results/batch-approve', { method: 'POST' }),
  runSchedule: (id) => request(`/schedules/${id}/run`, { method: 'POST' }),

  // 网站物料采集配置
  collectRegions: (refresh = false) => request(`/collect/regions?refresh=${refresh}`),
  refreshRegions: () => request('/collect/regions/refresh', { method: 'POST' }),
  collectConfigs: () => request('/collect/configs'),
  collectOverview: () => request('/collect/overview'),
  toggleSource: (id) => request(`/sources/${id}/toggle`, { method: 'POST' }),
  batchToggleCollect: (sourceId, enabled) =>
    request('/collect/configs/batch-toggle', {
      method: 'POST',
      body: JSON.stringify({ sourceId, enabled })
    }),
  searchCollect: (payload) =>
    request('/collect/search', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  createCollect: (payload) =>
    request('/collect/configs', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateCollect: (id, payload) =>
    request(`/collect/configs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  toggleCollect: (id) => request(`/collect/configs/${id}/toggle`, { method: 'POST' }),
  verifyCollect: (id) => request(`/collect/configs/${id}/verify`, { method: 'POST' }),
  backfillCollect: (id, payload) =>
    request(`/collect/configs/${id}/backfill`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  deleteCollect: (id) => request(`/collect/configs/${id}`, { method: 'DELETE' }),

  // 富宝 token 录入与自动续期
  collectTokenStatus: () => request('/collect/token'),
  saveCollectToken: (token) =>
    request('/collect/token', {
      method: 'POST',
      body: JSON.stringify({ token })
    }),
  refreshCollectToken: () =>
    request('/collect/token/refresh', { method: 'POST' }),
  saveCollectCredentials: (username, password) =>
    request('/collect/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    }),
  deleteCollectCredentials: () =>
    request('/collect/credentials', { method: 'DELETE' })
}

export default api
