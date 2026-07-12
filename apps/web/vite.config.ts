import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import cesium from 'vite-plugin-cesium'

export default defineConfig(({ mode }) => {
  const envDir = path.resolve(__dirname, '../..')
  const env = loadEnv(mode, envDir, '')
  const cfPort = env.CITYFORESIGHT_DEV_PORT || '8000'
  const usPort = env.URBANSENSE_DEV_PORT || '8001'
  const cgPort = env.CITYGUIDE_DEV_PORT || '8002'
  const tsPort = env.THERMALSCAPE_DEV_PORT || '8003'

  return {
    plugins: [
      react(),
      // Cesium is hoisted to the monorepo root node_modules.
      cesium({
        cesiumBuildRootPath: path.resolve(__dirname, '../../node_modules/cesium/Build'),
        cesiumBuildPath: path.resolve(__dirname, '../../node_modules/cesium/Build/Cesium'),
      }),
    ],
    envDir,
    server: {
      proxy: {
        '/api/guide': {
          target: `http://localhost:${cgPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/guide/, ''),
        },
        '/api/thermal': {
          target: `http://localhost:${tsPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/thermal/, ''),
        },
        '/api/sense': {
          target: `http://localhost:${usPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/sense/, ''),
        },
        '/api': {
          target: `http://localhost:${cfPort}`,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
  }
})
