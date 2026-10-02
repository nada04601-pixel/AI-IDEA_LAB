<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const jobId = route.params.id as string

interface MergeProposal {
  id: number
  canonical_name: string
  variants: { name: string; rows: number }[]
  is_applied: boolean
}

interface ErrorRow {
  row_number: number
  column_name: string
  raw_value: string
  reason_message: string
}

const loading = ref(false)
const generating = ref(false)
const mergeProposals = ref<MergeProposal[]>([])
const errorRows = ref<ErrorRow[]>([])
const validRowsCount = ref(0)
const errorPolicy = ref<'exclude' | 'abort'>('exclude')

async function fetchNormalizationData() {
  loading.value = true
  try {
    const res = await apiClient.get(`/jobs/${jobId}/normalization`)
    mergeProposals.value = res.data.merge_proposals || []
    errorRows.value = res.data.error_rows || []
    validRowsCount.value = res.data.valid_rows_count || 0
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

async function handleGenerate() {
  generating.value = true
  try {
    const appliedRuleIds = mergeProposals.value
      .filter((p) => p.is_applied)
      .map((p) => p.id)

    await apiClient.post(`/jobs/${jobId}/generate`, {
      error_policy: errorPolicy.value,
      applied_merge_rule_ids: appliedRuleIds,
    })

    ElMessage.success('보고서 생성이 시작되었습니다.')
    router.push(`/jobs/${jobId}/result`)
  } catch {
    // Error handled by interceptor
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  fetchNormalizationData()
})
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="5" />

    <el-card class="content-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>5단계: 데이터 정규화 및 보고서 생성</h2>
          <p class="subtitle">날짜, 금액 정규화 결과와 거래처 통합 제안을 확인해주세요.</p>
        </div>
      </template>

      <!-- 정상 행 요약 -->
      <div class="summary-box">
        <el-alert
          :title="`정상 데이터 ${validRowsCount.toLocaleString()}건이 확인되었습니다.`"
          type="success"
          :closable="false"
          show-icon
        />
      </div>

      <!-- 거래처명 통합 제안 (BR-06: 기본 미적용, 사용자 선택 시에만 적용) -->
      <div v-if="mergeProposals.length > 0" class="section-block">
        <h3>거래처명 통합 제안</h3>
        <p class="section-desc">표기가 조금씩 다른 거래처명을 하나의 이름으로 묶어 집계할 수 있습니다. 적용할 항목을 선택해주세요.</p>
        <el-table :data="mergeProposals" border stripe>
          <el-table-column width="60" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.is_applied" />
            </template>
          </el-table-column>
          <el-table-column prop="canonical_name" label="통합 기준 명칭" width="180" />
          <el-table-column label="통합 대상 표기 및 건수">
            <template #default="{ row }">
              <el-tag
                v-for="(v, vIdx) in row.variants"
                :key="vIdx"
                size="small"
                type="info"
                style="margin-right: 0.4rem; margin-bottom: 0.2rem;"
              >
                {{ v.name }} ({{ v.rows }}건)
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 오류 행 목록 -->
      <div v-if="errorRows.length > 0" class="section-block">
        <h3 style="color: #e6a23c;">정규화 실패 행 (총 {{ errorRows.length }}건)</h3>
        <p class="section-desc">날짜 또는 금액 형식이 올바르지 않은 행입니다.</p>
        <el-table :data="errorRows" border stripe max-height="250">
          <el-table-column prop="row_number" label="행 번호" width="90" align="center" />
          <el-table-column prop="column_name" label="컬럼명" width="140" />
          <el-table-column prop="raw_value" label="원본 입력값" min-width="160" />
          <el-table-column prop="reason_message" label="오류 사유" min-width="200" />
        </el-table>

        <div class="policy-choice">
          <span style="font-weight: 600; margin-right: 1rem;">오류 행 처리:</span>
          <el-radio-group v-model="errorPolicy">
            <el-radio value="exclude">오류 행을 제외하고 정상 데이터만으로 보고서 생성</el-radio>
            <el-radio value="abort">생성 중단 (원본 파일 수정 후 재업로드)</el-radio>
          </el-radio-group>
        </div>
      </div>

      <div class="btn-group">
        <el-button @click="router.push(`/jobs/${jobId}/mapping`)">이전 (매핑 수정)</el-button>
        <el-button
          type="primary"
          size="large"
          :loading="generating"
          :disabled="errorRows.length > 0 && errorPolicy === 'abort'"
          @click="handleGenerate"
        >
          보고서 생성 시작
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
.summary-box {
  margin-bottom: 1.5rem;
}
.section-block {
  margin-top: 2rem;
}
.section-block h3 {
  margin: 0 0 0.4rem 0;
}
.section-desc {
  margin: 0 0 0.8rem 0;
  color: #909399;
  font-size: 0.9rem;
}
.policy-choice {
  margin-top: 1.2rem;
  background-color: #fdf6ec;
  padding: 1rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
}
.btn-group {
  margin-top: 2.5rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
</style>
