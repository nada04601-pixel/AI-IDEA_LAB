<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import apiClient from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isSignup = ref(false)
const loading = ref(false)

const form = reactive({
  email: '',
  password: '',
  passwordConfirm: '',
})

async function handleSubmit() {
  if (!form.email || !form.password) {
    ElMessage.warning('이메일과 비밀번호를 입력해주세요.')
    return
  }

  if (isSignup.value && form.password !== form.passwordConfirm) {
    ElMessage.warning('비밀번호가 일치하지 않습니다.')
    return
  }

  loading.value = true
  try {
    if (isSignup.value) {
      await apiClient.post('/auth/signup', {
        email: form.email,
        password: form.password,
        password_confirm: form.passwordConfirm,
      })
      ElMessage.success('회원가입이 완료되었습니다. 로그인해주세요.')
      isSignup.value = false
    } else {
      const res = await apiClient.post('/auth/login', {
        email: form.email,
        password: form.password,
      })
      authStore.setUser(res.data.user)
      ElMessage.success('로그인되었습니다.')
      router.push('/')
    }
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>AI Excel 보고서 자동생성기</h2>
          <p class="subtitle">{{ isSignup ? '회원가입' : '로그인' }}</p>
        </div>
      </template>

      <el-form :model="form" label-position="top">
        <el-form-item label="이메일">
          <el-input v-model="form.email" placeholder="example@company.com" type="email" />
        </el-form-item>

        <el-form-item label="비밀번호">
          <el-input v-model="form.password" placeholder="비밀번호 (8자 이상)" type="password" show-password />
        </el-form-item>

        <el-form-item v-if="isSignup" label="비밀번호 확인">
          <el-input v-model="form.passwordConfirm" placeholder="비밀번호 재입력" type="password" show-password />
        </el-form-item>

        <el-button type="primary" :loading="loading" class="submit-btn" @click="handleSubmit">
          {{ isSignup ? '회원가입' : '로그인' }}
        </el-button>

        <div class="toggle-link">
          <el-link type="info" @click="isSignup = !isSignup">
            {{ isSignup ? '이미 계정이 있으신가요? 로그인' : '처음이신가요? 회원가입' }}
          </el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-container {
  min-height: 80vh;
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-card {
  width: 420px;
  max-width: 90%;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.card-header h2 {
  font-size: 1.3rem;
  margin: 0 0 0.5rem 0;
  text-align: center;
  color: #303133;
}

.subtitle {
  margin: 0;
  text-align: center;
  color: #909399;
  font-size: 0.95rem;
}

.submit-btn {
  width: 100%;
  margin-top: 1rem;
}

.toggle-link {
  margin-top: 1.2rem;
  text-align: center;
}
</style>
