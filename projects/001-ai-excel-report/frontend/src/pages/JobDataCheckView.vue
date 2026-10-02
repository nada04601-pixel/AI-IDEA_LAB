<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const jobId = route.params.id as string

interface ColumnProfile {
  index: number
  name: string
  type: string
  empty_ratio: number
  distinct: number
  samples: string[]
}

const loading = ref(false)
const totalRows = ref(0)
const totalColumns = ref(0)
const columns = ref<ColumnProfile[]>([])
const warnings = ref<string[]>([])

async function fetchDataProfile() {
  loading.value = true
  try {
    const res = await apiClient.get(`/jobs/${jobId}/data`)
    totalRows.value = res.data.total_rows || 0
    totalColumns.value = res.data.total_columns || 0
    columns.value = res.data.columns || []
    warnings.value = res.data.warnings || []
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

function handleNext() {
  router.push(`/jobs/${jobId}/mapping`)
}

onMounted(() => {
  fetchDataProfile()
})
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="3" />

    <el-card class="content-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>3단계: 원본 데이터 분석 결과</h2>
          <p class="subtitle">업로드된 파일의 구조와 컬럼 정보를 확인해주세요.</p>
        </div>
      </template>

      <!-- 요약 통계 -->
      <el-row :gutter="20" class="stat-row">
        <el-col :span="12">
          <el-statistic title="총 데이터 행 수" :value="totalRows" suffix="행" />
        </el-col>
        <el-col :span="12">
          <el-statistic title="감지된 컬럼 수" :value="totalColumns" suffix="개" />
        </el-col>
      </el-row>

      <!-- 경고 알림 -->
      <div v-if="warnings.length > 0" class="warning-section">
        <el-alert
          v-for="(w, idx) in warnings"
          :key="idx"
          :title="w"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 0.5rem;"
        />
      </div>

      <!-- 컬럼 목록 테이블 -->
      <h3>컬럼 상세 프로파일</h3>
      <el-table :data="columns" stripe border style="width: 100%">
        <el-table-column prop="index" label="순번" width="70" align="center" />
        <el-table-column prop="name" label="컬럼명" min-width="140" />
        <el-table-column prop="type" label="추정 타입" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.type === 'number' ? 'success' : row.type === 'date' ? 'warning' : 'info'">
              {{ row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="빈 값 비율" width="110" align="center">
          <template #default="{ row }">
            {{ (row.empty_ratio * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="샘플 데이터" min-width="260">
          <template #default="{ row }">
            <el-tag
              v-for="(s, sIdx) in row.samples"
              :key="sIdx"
              size="small"
              type="info"
              style="margin-right: 0.3rem; margin-bottom: 0.2rem;"
            >
              {{ s }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="btn-group">
        <el-button @click="router.push(`/jobs/${jobId}/template`)">이전 (템플릿 선택)</el-button>
        <el-button type="primary" @click="handleNext">
          다음 (컬럼 매핑)
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.step-page-container {
  max-width: 950px;
  margin: 0 auto;
}
.content-card {
  border-radius: 8px;
}
.card-header h2 {
  margin: 0 0 0.3rem 0;
  font-size: 1.4rem;
}
.subtitle {
  margin: 0;
  color: #909399;
}
.stat-row {
  margin-bottom: 1.5rem;
  background-color: #fafafa;
  padding: 1rem;
  border-radius: 8px;
}
.warning-section {
  margin-bottom: 1.5rem;
}
.btn-group {
  margin-top: 2rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
</style>
