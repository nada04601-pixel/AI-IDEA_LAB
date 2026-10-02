<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'
import { useJobStore } from '@/stores/job'

const route = useRoute()
const router = useRouter()
const jobStore = useJobStore()
const jobId = route.params.id as string

interface Template {
  id: number
  name: string
  description: string
  fields: {
    field_key: string
    field_name: string
    data_type: string
    is_required: boolean
    ai_hint?: string
  }[]
}

const templates = ref<Template[]>([])
const selectedTemplateId = ref<number | null>(null)
const loading = ref(false)
const submitting = ref(false)

async function fetchTemplates() {
  loading.value = true
  try {
    const res = await apiClient.get('/templates')
    templates.value = res.data.templates || []
    if (templates.value.length > 0 && !selectedTemplateId.value) {
      selectedTemplateId.value = templates.value[0].id
    }
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

async function handleNext() {
  if (!selectedTemplateId.value) {
    ElMessage.warning('보고서 템플릿을 선택해주세요.')
    return
  }

  submitting.value = true
  try {
    await apiClient.post(`/jobs/${jobId}/template`, {
      template_id: selectedTemplateId.value,
    })
    jobStore.setJob({ templateId: selectedTemplateId.value, currentStep: 3 })
    router.push(`/jobs/${jobId}/data`)
  } catch {
    // Error handled by interceptor
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchTemplates()
})
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="2" />

    <el-card class="content-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>2단계: 보고서 템플릿 선택</h2>
          <p class="subtitle">생성할 보고서의 양식을 선택해주세요.</p>
        </div>
      </template>

      <div class="template-list">
        <el-radio-group v-model="selectedTemplateId" class="radio-cards">
          <div
            v-for="tpl in templates"
            :key="tpl.id"
            class="template-card"
            :class="{ active: selectedTemplateId === tpl.id }"
            @click="selectedTemplateId = tpl.id"
          >
            <div class="card-top">
              <el-radio :value="tpl.id" class="radio-btn">
                <span class="tpl-name">{{ tpl.name }}</span>
              </el-radio>
            </div>
            <p class="tpl-desc">{{ tpl.description }}</p>

            <el-divider style="margin: 0.8rem 0;" />
            <div class="required-fields">
              <span class="field-title">요구 필드:</span>
              <el-tag
                v-for="f in tpl.fields"
                :key="f.field_key"
                size="small"
                :type="f.is_required ? 'danger' : 'info'"
                class="field-tag"
              >
                {{ f.field_name }} {{ f.is_required ? '*' : '' }}
              </el-tag>
            </div>
          </div>
        </el-radio-group>
      </div>

      <div class="btn-group">
        <el-button @click="router.push('/jobs/new')">이전 (파일 재업로드)</el-button>
        <el-button type="primary" :loading="submitting" @click="handleNext">
          다음 (데이터 확인)
        </el-button>
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
}
.card-header h2 {
  margin: 0 0 0.3rem 0;
  font-size: 1.4rem;
}
.subtitle {
  margin: 0;
  color: #909399;
}
.radio-cards {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}
.template-card {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 1.2rem;
  cursor: pointer;
  transition: all 0.2s ease;
  width: 100%;
}
.template-card:hover {
  border-color: #409eff;
}
.template-card.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}
.card-top {
  display: flex;
  align-items: center;
}
.tpl-name {
  font-weight: 600;
  font-size: 1.05rem;
  margin-left: 0.4rem;
}
.tpl-desc {
  margin: 0.5rem 0 0 1.8rem;
  color: #606266;
  font-size: 0.9rem;
}
.required-fields {
  margin-left: 1.8rem;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.field-title {
  font-size: 0.85rem;
  color: #909399;
  margin-right: 0.4rem;
}
.field-tag {
  margin-right: 0.2rem;
}
.btn-group {
  margin-top: 2rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
</style>
