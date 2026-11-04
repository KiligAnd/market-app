import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      // 后续接入 FastAPI + SQLite 时，把 /api 代理到本地服务即可。
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
