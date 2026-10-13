/** 模块职责：配置 React/Tailwind 构建插件和本地开发 API 反向代理。 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 开发环境保持与生产一致的同源 /api 路径，避免组件感知后端端口和 CORS 差异。
      "/api": "http://localhost:8000",
    },
  },
})
