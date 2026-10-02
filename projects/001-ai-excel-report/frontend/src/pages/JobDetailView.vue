<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, RefreshRight, ArrowLeft } from '@element-plus/icons-vue'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const jobId = route.params.id as string

const loading = ref(false)
const job = ref<any>(null)

async function fetchJobDetail() {
  loading.value = true
  try {
    const res = await apiClient.get(`/jobs/${jobId}`)
    job.value = res.data
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('이 작업과 생성된 결과 파일을 정말 삭제하시겠습니까?', '작업 삭제 확인', {
      confirmButtonText: '삭제',
      cancelButtonText: '취소',
      type: 'warning',
    })

    await apiClient.delete(`/jobs/${jobId}`)
    ElMessage.success('작업이 삭제되었습니다.')
    router.push('/')
  } catch {
    // cancelled or error
  }
}

function handleDownload() {
  if (job.value?.result_file?.id) {
    window.open(`/api/v1/files/${job.value.result_file.id}/download`, '_blank')
  }
}

function handleReuseMapping() {
  router.push(`/jobs/new?reuse_job_id=${jobId}`)
}

onMounted(() => {
  fetchJobDetail()
})
</script>

<template>
  <div class="detail-container" v-loading="loading">
    <div class="top-nav">
      <el-button :icon="ArrowLeft" text @click="router.push('/')">목록으로 돌아가기</el-button>
    </div>

    <el-card v-if="job" class="detail-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>작업 상세 정보</h2>
            <p class="subtitle">{{ job.original_file_name }}</p>
          </div>
          <div class="header-actions">
            <el-button
              v-if="job.result_file && !job.result_file.is_expired"
              type="success"
              :icon="Download"
              @click="handleDownload"
            >
              보고서 다운로드
            </el-button>
            <el-button type="primary" :icon="RefreshRight" @click="handleReuseMapping">
              이 매핑으로 새 작업
            </el-button>
            <el-button type="danger" :icon="Delete" @click="handleDelete">
              삭제
            </el-button>
          </div>
        </div>
      </template>

      <!-- 기본 정보 -->
      <el-descriptions title="기본 정보" :column="2" border style="margin-bottom: 2rem;">
        <el-descriptions-item label="작업 ID">{{ job.id }}</el-descriptions-item>
        <el-descriptions-item label="생성 일시">
          {{ new Date(job.created_at).toLocaleString('ko-KR') }}
        </el-descriptions-item>
        <el-descriptions-item label="적용 템플릿">{{ job.template_name }}</el-descriptions-item>
        <el-descriptions-item label="작업 상태">
          <el-tag :type="job.status === 'succeeded' ? 'success' : 'danger'">
            {{ job.status === 'succeeded' ? '완료' : '실패' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="반영 행 수">
          {{ job.processed_rows?.toLocaleString() ?? '-' }}행
        </el-descriptions-item>
        <el-descriptions-item label="제외 행 수">
          {{ job.excluded_rows?.toLocaleString() ?? '-' }}행
        </el-descriptions-item>
      </el-descriptions>

      <!-- 매핑 설정 내역 -->
      <h3>컬럼 매핑 내역</h3>
      <el-table :data="job.mappings || []" border stripe style="margin-bottom: 2rem;">
        <el-table-column prop="field_name" label="보고서 필드" min-width="140" />
        <el-table-column prop="source_column_name" label="매핑된 원본 컬럼" min-width="160">
          <template #default="{ row }">
            <el-tag v-if="row.source_column_name" size="small">{{ row.source_column_name }}</el-tag>
            <span v-else style="color: #909399;">(미선택)</span>
          </template>
        </el-table-column>
        <el-table-column prop="origin" label="설정 출처" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.origin }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 집계 요약 -->
      <div v-if="job.summary">
        <h3>집계 요약</h3>
        <pre class="json-summary">{{ JSON.stringify(job.summary, null, 2) }}</pre>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.detail-container {
  max-width: 1000px;
  margin: 0 auto;
}
.top-nav {
  margin-bottom: 1rem;
}
.detail-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header h2 {
  margin: 0 0 0.3rem 0;
  font-size: 1.4rem;
}
.subtitle {
  margin: 0;
  color: #909399;
}
.header-actions {
  display: flex;
  gap: 0.5rem;
}
.json-summary {
  background-color: #f8f9fa;
  padding: 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  overflow-x: auto;
}
</style>
