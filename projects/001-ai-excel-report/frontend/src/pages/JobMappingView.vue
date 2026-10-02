<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const jobId = route.params.id as string

interface SourceColumn {
  index: number
  name: string
  type: string
}

interface MappingItem {
  field_id: number
  field_key: string
  field_name: string
  data_type: string
  is_required: boolean
  source_column_index: number | null
  confidence: 'high' | 'medium' | 'low' | 'none'
  reason: string | null
  origin: string
}

const loading = ref(false)
const submitting = ref(false)
const sourceColumns = ref<SourceColumn[]>([])
const mappings = ref<MappingItem[]>([])

async function fetchMappings() {
  loading.value = true
  try {
    const res = await apiClient.get(`/jobs/${jobId}/mapping`)
    sourceColumns.value = res.data.source_columns || []
    mappings.value = res.data.mappings || []
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

// 중복 선택된 컬럼 인덱스 감지
const duplicateIndexes = computed(() => {
  const counts: Record<number, number> = {}
  for (const m of mappings.value) {
    if (m.source_column_index !== null) {
      counts[m.source_column_index] = (counts[m.source_column_index] || 0) + 1
    }
  }
  return Object.keys(counts)
    .filter((k) => counts[Number(k)] > 1)
    .map(Number)
})

// 필수 항목 누락 여부
const missingRequired = computed(() => {
  return mappings.value.some((m) => m.is_required && m.source_column_index === null)
})

async function handleSave() {
  if (missingRequired.value) {
    ElMessage.error('필수 항목(*)의 원본 컬럼을 모두 선택해주세요.')
    return
  }

  if (duplicateIndexes.value.length > 0) {
    ElMessage.error('하나의 원본 컬럼을 여러 필드에 중복으로 매핑할 수 없습니다.')
    return
  }

  submitting.value = true
  try {
    const payload = {
      mappings: mappings.value.map((m) => ({
        field_id: m.field_id,
        source_column_index: m.source_column_index,
      })),
    }

    await apiClient.post(`/jobs/${jobId}/mapping`, payload)
    ElMessage.success('컬럼 매핑이 확정되었습니다.')
    router.push(`/jobs/${jobId}/normalization`)
  } catch {
    // Error handled by interceptor
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchMappings()
})
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="4" />

    <el-card class="content-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>4단계: 컬럼 매핑</h2>
          <p class="subtitle">보고서의 각 필드에 연결할 원본 데이터 컬럼을 확인하고 지정해주세요.</p>
        </div>
      </template>

      <el-alert
        v-if="duplicateIndexes.length > 0"
        title="중복 매핑 경고: 동일한 원본 컬럼이 여러 필드에 선택되었습니다."
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 1rem;"
      />

      <el-table :data="mappings" stripe border style="width: 100%">
        <el-table-column label="보고서 필드" min-width="150">
          <template #default="{ row }">
            <strong>{{ row.field_name }}</strong>
            <span v-if="row.is_required" style="color: #f56c6c; margin-left: 4px;">*</span>
            <div style="font-size: 0.8rem; color: #909399;">
              타입: {{ row.data_type }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="매핑할 원본 컬럼" min-width="200">
          <template #default="{ row }">
            <el-select
              v-model="row.source_column_index"
              placeholder="컬럼 선택 (선택 안 함 가능)"
              clearable
              style="width: 100%;"
              :class="{ 'is-duplicate': row.source_column_index !== null && duplicateIndexes.includes(row.source_column_index) }"
            >
              <el-option
                v-for="col in sourceColumns"
                :key="col.index"
                :label="`${col.name} (${col.type})`"
                :value="col.index"
              />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="AI 추천 신뢰도" width="130" align="center">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.confidence === 'high' ? 'success' : row.confidence === 'medium' ? 'warning' : 'info'"
            >
              {{ row.confidence === 'high' ? '높음' : row.confidence === 'medium' ? '보통' : row.confidence === 'low' ? '낮음' : '직접선택' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="추천 근거" min-width="180">
          <template #default="{ row }">
            <span style="font-size: 0.85rem; color: #606266;">
              {{ row.reason || '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="btn-group">
        <el-button @click="router.push(`/jobs/${jobId}/data`)">이전 (데이터 확인)</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="missingRequired || duplicateIndexes.length > 0"
          @click="handleSave"
        >
          다음 (정규화 및 생성)
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
.btn-group {
  margin-top: 2rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
</style>
