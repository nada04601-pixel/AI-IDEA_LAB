<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Download, View } from '@element-plus/icons-vue'
import apiClient from '@/api/client'

const router = useRouter()

interface JobItem {
  id: string
  created_at: string
  original_file_name: string
  template_name: string
  processed_rows: number | null
  excluded_rows: number | null
  status: 'succeeded' | 'failed'
  result_file: {
    id: string
    is_expired: boolean
  } | null
}

const jobs = ref<JobItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)

async function fetchJobs() {
  loading.value = true
  try {
    const res = await apiClient.get('/jobs', {
      params: { page: page.value, page_size: 20 },
    })
    jobs.value = res.data.items || []
    total.value = res.data.total || 0
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

function startNewJob() {
  router.push('/jobs/new')
}

function goToDetail(id: string) {
  router.push(`/history/${id}`)
}

function downloadResult(fileId: string) {
  window.open(`/api/v1/files/${fileId}/download`, '_blank')
}

onMounted(() => {
  fetchJobs()
})
</script>

<template>
  <div class="history-container">
    <div class="header-section">
      <div>
        <h1>작업 이력</h1>
        <p class="desc">이전에 생성한 보고서 목록입니다. 30일 이내에 다시 다운로드할 수 있습니다.</p>
      </div>
      <el-button type="primary" :icon="Plus" size="large" @click="startNewJob">
        새 보고서 만들기
      </el-button>
    </div>

    <el-card class="table-card">
      <el-table :data="jobs" v-loading="loading" stripe empty-text="아직 생성된 보고서 이력이 없습니다.">
        <el-table-column prop="created_at" label="생성 일시" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('ko-KR') }}
          </template>
        </el-table-column>
        <el-table-column prop="original_file_name" label="원본 파일" min-width="180" />
        <el-table-column prop="template_name" label="보고서 양식" min-width="160" />
        <el-table-column label="처리 건수" width="130" align="center">
          <template #default="{ row }">
            <span v-if="row.processed_rows !== null">
              {{ row.processed_rows.toLocaleString() }}행
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="상태" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'succeeded' ? 'success' : 'danger'">
              {{ row.status === 'succeeded' ? '완료' : '실패' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="작업" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" :icon="View" @click="goToDetail(row.id)">
              상세
            </el-button>
            <el-button
              v-if="row.result_file && !row.result_file.is_expired"
              size="small"
              type="success"
              :icon="Download"
              @click="downloadResult(row.result_file.id)"
            >
              다운로드
            </el-button>
            <el-tag v-else-if="row.result_file?.is_expired" type="info" size="small">
              만료됨
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-section" v-if="total > 20">
        <el-pagination
          v-model:current-page="page"
          :page-size="20"
          :total="total"
          layout="prev, pager, next"
          @current-change="fetchJobs"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.history-container {
  max-width: 1200px;
  margin: 0 auto;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-section h1 {
  font-size: 1.6rem;
  margin: 0 0 0.4rem 0;
  color: #303133;
}

.desc {
  margin: 0;
  color: #909399;
}

.table-card {
  border-radius: 8px;
}

.pagination-section {
  margin-top: 1.5rem;
  display: flex;
  justify-content: center;
}
</style>
