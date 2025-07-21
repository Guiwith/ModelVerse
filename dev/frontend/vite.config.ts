import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 开发环境API代理设置
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://172.31.118.255:8888',
        changeOrigin: true,
        secure: false
      },
      '/token': {
        target: process.env.VITE_API_URL || 'http://172.31.118.255:8888',
        changeOrigin: true,
        secure: false
      },
      '/static': {
        target: process.env.VITE_API_URL || 'http://172.31.118.255:8888',
        changeOrigin: true,
        secure: false
      },
      '/uploads': {
        target: process.env.VITE_API_URL || 'http://172.31.118.255:8888',
        changeOrigin: true,
        secure: false
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    // 生产环境构建配置
    outDir: '../backend/static',
    emptyOutDir: true
  }
}) 