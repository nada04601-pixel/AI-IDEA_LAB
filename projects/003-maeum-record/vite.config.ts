import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// 화면에 표시할 빌드 번호: CI는 실행 번호, 로컬 빌드는 빌드 시각 (업데이트됐는지 확인용)
const stamp = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 16).replace(/[-:]/g, '').replace('T', '-')
const APP_BUILD = process.env.GITHUB_RUN_NUMBER ? `0.1.${process.env.GITHUB_RUN_NUMBER}` : `0.1.0+${stamp}`

export default defineConfig({
  define: { __APP_BUILD__: JSON.stringify(APP_BUILD) },
  base: './',
  plugins: [
    vue(),
    VitePWA({
      // Capacitor 앱 빌드에서는 서비스 워커가 필요 없다 (파일이 앱에 포함됨)
      disable: !!process.env.CAPACITOR,
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: '마음기록',
        short_name: '마음기록',
        description: '하루 한 번 기분을 기록하고, 진료·상담에 가져갈 수 있는 기록 도구',
        lang: 'ko',
        start_url: './',
        scope: './',
        display: 'standalone',
        background_color: '#f7f6f2',
        theme_color: '#f7f6f2',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      workbox: { globPatterns: ['**/*.{js,css,html,svg,png}'] },
    }),
  ],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
})
