import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  return {
    plugins: [vue()],
    server: {
      port: 5174,
      strictPort: true,
      proxy: {
        '/api/python': {
          target: env.VITE_PYTHON_API_URL || 'http://127.0.0.1:8003',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/python/, '')
        },
        '/api/java': {
          target: env.VITE_JAVA_API_URL || 'http://localhost:8080',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/java/, '')
        }
      }
    }
  }
})
