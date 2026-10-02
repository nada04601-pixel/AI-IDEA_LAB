<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Document, Plus, SwitchButton } from '@element-plus/icons-vue'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

async function handleLogout() {
  try {
    await apiClient.post('/auth/logout')
  } catch {
    // ignore
  } finally {
    authStore.clearUser()
    router.push('/login')
  }
}
</script>

<template>
  <el-container class="app-layout">
    <el-header v-if="route.path !== '/login'" class="app-header">
      <div class="logo-area" @click="router.push('/')">
        <el-icon class="logo-icon"><Document /></el-icon>
        <span class="logo-title">AI Excel 보고서 자동생성기</span>
        <el-tag size="small" type="success" effect="plain" round style="margin-left: 0.5rem;">체험 모드 (Demo)</el-tag>
      </div>

      <div class="nav-actions">
        <el-button type="primary" :icon="Plus" size="default" @click="router.push('/jobs/new')">
          새 보고서 작성
        </el-button>
        <el-button :icon="SwitchButton" size="default" text @click="handleLogout">
          로그아웃
        </el-button>
      </div>
    </el-header>

    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
/* Global resets */
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
  color: #303133;
}
</style>

<style scoped>
.app-layout {
  min-height: 100vh;
}
.app-header {
  background-color: #ffffff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
  height: 64px;
}
.logo-area {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 0.5rem;
}
.logo-icon {
  font-size: 1.5rem;
  color: #409eff;
}
.logo-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: #303133;
}
.nav-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.app-main {
  padding: 2rem;
}
</style>
