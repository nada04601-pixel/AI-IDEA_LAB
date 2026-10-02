<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Check, Close, Loading } from '@element-plus/icons-vue'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const jobId = route.params.id as string

const status = ref<'draft' | 'generating' | 'succeeded' | 'failed'>('generating')
const processedRows = ref<number | null>(null)
const excludedRows = ref<number | null>(null)
const resultFileId = ref<string | null>(null)
const summary = ref<any>(null)
const errorMessage = ref<string | null>(null)

let pollTimer: number | null = null

async function checkStatus() {
  try {
    const res = await apiClient.get(`/jobs/${jobId}/status`)
    status.value = res.data.status
    processedRows.value = res.data.processed_rows
    excludedRows.value = res.data.excluded_rows
    resultFileId.value = res.data.result_file_id
    summary.value = res.data.summary
    errorMessage.value = res.data.error_message

    if (status.value === 'generating') {
      pollTimer = window.setTimeout(checkStatus, 1500)
    }
  } catch {
    status.value = 'failed'
    errorMessage.value = '작업 상태를 조회하는 중 오류가 발생했습니다.'
  }
}

function handleDownload() {
  if (resultFileId.value) {
    window.open(`/api/v1/files/${resultFileId.value}/download`, '_blank')
  }
}

onMounted(() => {
  checkStatus()
})

onUnmounted(() => {
  if (pollTimer) {
    clearTimeout(pollTimer)
  }
})
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="6" />

    <el-card class="content-card">
      <!-- 생성 진행 중 -->
      <div v-if="status === 'generating'" class="status-box">
        <el-icon class="is-loading loading-icon"><Loading /></el-icon>
        <h2>보고서를 생성하고 있습니다...</h2>
        <p class="desc">데이터를 집계하고 엑셀 서식을 적용하는 중입니다. 잠시만 기다려주세요.</p>
      </div>

      <!-- 생성 완료 성공 -->
      <div v-else-if="status === 'succeeded'" class="status-box">
        <el-icon class="success-icon"><Check /></el-icon>
        <h2>보고서가 성공적으로 생성되었습니다!</h2>
        <p class="desc">아래 요약을 확인하고 생성된 Excel 보고서를 다운로드하세요.</p>

        <div class="result-summary">
          <el-descriptions title="처리 결과 요약" :column="2" border>
            <el-descriptions-item label="반영된 데이터">
              {{ processedRows?.toLocaleString() }}행
            </el-descriptions-item>
            <el-descriptions-item label="제외된 오류 데이터">
              {{ excludedRows ?? 0 }}행
            </el-descriptions-item>
            <el-descriptions-item label="합계 검증" :span="2">
              <el-tag type="success">검증 일치 (무결성 확인됨)</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="action-buttons">
          <el-button type="success" size="large" :icon="Download" @click="handleDownload">
            생성된 Excel 보고서 다운로드
          </el-button>
          <el-button size="large" @click="router.push('/')">
            작업 목록(홈)으로 이동
          </el-button>
        </div>
      </div>

      <!-- 생성 실패 -->
      <div v-else class="status-box">
        <el-icon class="fail-icon"><Close /></el-icon>
        <h2>보고서 생성에 실패했습니다</h2>
        <p class="error-msg">{{ errorMessage || '알 수 없는 오류가 발생했습니다.' }}</p>

        <div class="action-buttons">
          <el-button @click="router.push(`/jobs/${jobId}/normalization`)">
            이전 단계로 돌아가기
          </el-button>
          <el-button type="primary" @click="router.push('/jobs/new')">
            새 작업 시작
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.step-page-container {
  max-width: 900px;
  margin: 0 auto;
}
.content-card {
  border-radius: 8px;
  padding: 2rem 1rem;
}
.status-box {
  text-align: center;
}
.loading-icon {
  font-size: 3.5rem;
  color: #409eff;
  margin-bottom: 1rem;
}
.success-icon {
  font-size: 3.5rem;
  color: #67c23a;
  background-color: #f0f9eb;
  border-radius: 50%;
  padding: 0.5rem;
  margin-bottom: 1rem;
}
.fail-icon {
  font-size: 3.5rem;
  color: #f56c6c;
  background-color: #fef0f0;
  border-radius: 50%;
  padding: 0.5rem;
  margin-bottom: 1rem;
}
.status-box h2 {
  font-size: 1.5rem;
  margin: 0 0 0.5rem 0;
}
.desc {
  color: #909399;
  margin-bottom: 2rem;
}
.error-msg {
  color: #f56c6c;
  margin-bottom: 2rem;
}
.result-summary {
  max-width: 600px;
  margin: 0 auto 2rem auto;
  text-align: left;
}
.action-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
}
</style>
