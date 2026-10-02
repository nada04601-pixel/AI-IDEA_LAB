<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import WizardSteps from '@/components/WizardSteps.vue'
import apiClient from '@/api/client'
import { useJobStore } from '@/stores/job'

const router = useRouter()
const jobStore = useJobStore()

const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const sheetList = ref<string[]>([])
const selectedSheet = ref('')
const headerRow = ref(1)
const uploadedFileId = ref<string | null>(null)
const createdJobId = ref<string | null>(null)

async function handleFileChange(uploadFile: UploadFile) {
  const rawFile = uploadFile.raw
  if (!rawFile) return

  if (rawFile.size > 10 * 1024 * 1024) {
    ElMessage.error('파일 크기는 10MB 이하만 가능합니다.')
    fileList.value = []
    return
  }

  const formData = new FormData()
  formData.append('file', rawFile)

  uploading.value = true
  try {
    const res = await apiClient.post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    uploadedFileId.value = res.data.file_id
    sheetList.value = res.data.sheets || []
    selectedSheet.value = res.data.default_sheet || res.data.sheets?.[0] || ''
    headerRow.value = res.data.detected_header_row || 1
    ElMessage.success('파일이 성공적으로 업로드되었습니다.')
  } catch {
    fileList.value = []
  } finally {
    uploading.value = false
  }
}

async function handleNext() {
  if (!uploadedFileId.value) {
    ElMessage.warning('먼저 파일을 업로드해주세요.')
    return
  }

  try {
    const res = await apiClient.post('/jobs', {
      source_file_id: uploadedFileId.value,
      sheet_name: selectedSheet.value || undefined,
      header_row: headerRow.value,
    })

    createdJobId.value = res.data.job_id
    jobStore.setJob({
      id: res.data.job_id,
      currentStep: 2,
      sheetName: selectedSheet.value,
      headerRow: headerRow.value,
    })
    router.push(`/jobs/${res.data.job_id}/template`)
  } catch {
    // Error handled by interceptor
  }
}
</script>

<template>
  <div class="step-page-container">
    <WizardSteps :active-step="1" />

    <el-card class="content-card">
      <template #header>
        <div class="card-header">
          <h2>1단계: 원본 데이터 업로드</h2>
          <p class="subtitle">분석할 Excel(.xlsx, .xls) 또는 CSV 파일을 업로드해주세요. (최대 10MB)</p>
        </div>
      </template>

      <el-upload
        drag
        action=""
        :auto-upload="false"
        :limit="1"
        :file-list="fileList"
        :on-change="handleFileChange"
        accept=".xlsx,.xls,.csv"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          파일을 이곳에 드래그하거나 <em>클릭하여 업로드</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            Excel 파일(.xlsx, .xls) 또는 CSV 파일 / 최대 10MB, 50,000행 이내
          </div>
        </template>
      </el-upload>

      <div v-if="uploadedFileId" class="upload-options">
        <el-divider />
        <h3>파일 설정</h3>
        <el-form label-position="top">
          <el-form-item v-if="sheetList.length > 1" label="데이터가 포함된 시트">
            <el-select v-model="selectedSheet" placeholder="시트 선택">
              <el-option v-for="sheet in sheetList" :key="sheet" :label="sheet" :value="sheet" />
            </el-select>
          </el-form-item>

          <el-form-item label="헤더(컬럼명) 행 번호">
            <el-input-number v-model="headerRow" :min="1" :max="20" />
            <span class="hint">일반적으로 1행에 컬럼명이 있습니다. 제목 등이 윗 행에 있으면 조정해주세요.</span>
          </el-form-item>
        </el-form>
      </div>

      <div class="btn-group">
        <el-button @click="router.push('/')">취소</el-button>
        <el-button type="primary" :disabled="!uploadedFileId" :loading="uploading" @click="handleNext">
          다음 (템플릿 선택)
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
.upload-options {
  margin-top: 1.5rem;
}
.hint {
  margin-left: 1rem;
  color: #909399;
  font-size: 0.85rem;
}
.btn-group {
  margin-top: 2rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
</style>
