import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface JobState {
  id: string | null
  currentStep: number
  templateId: number | null
  originalFileName: string | null
  sheetName: string | null
  headerRow: number
  totalRows: number | null
  status: 'draft' | 'generating' | 'succeeded' | 'failed' | null
}

export const useJobStore = defineStore('job', () => {
  const currentJob = ref<JobState>({
    id: null,
    currentStep: 1,
    templateId: null,
    originalFileName: null,
    sheetName: null,
    headerRow: 1,
    totalRows: null,
    status: null,
  })

  function setJob(job: Partial<JobState>) {
    currentJob.value = { ...currentJob.value, ...job }
  }

  function resetJob() {
    currentJob.value = {
      id: null,
      currentStep: 1,
      templateId: null,
      originalFileName: null,
      sheetName: null,
      headerRow: 1,
      totalRows: null,
      status: null,
    }
  }

  return {
    currentJob,
    setJob,
    resetJob,
  }
})
