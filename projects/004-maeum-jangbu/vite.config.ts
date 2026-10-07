import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 화면에 표시할 빌드 번호: CI는 실행 번호, 로컬 빌드는 빌드 시각 (업데이트됐는지 확인용)
const stamp = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 16).replace(/[-:]/g, '').replace('T', '-')
const APP_BUILD = process.env.GITHUB_RUN_NUMBER ? `0.1.${process.env.GITHUB_RUN_NUMBER}` : `0.1.0+${stamp}`

// 앱 우선(tech-stack.md 1장)이라 PWA 설정은 두지 않는다. 웹 빌드는 개발·확인용.
export default defineConfig({
  define: { __APP_BUILD__: JSON.stringify(APP_BUILD) },
  base: './',
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
})
