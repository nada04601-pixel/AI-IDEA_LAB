<script setup lang="ts">
defineProps<{
  activeStep: number
}>()

const steps = [
  { title: '파일 업로드', step: 1 },
  { title: '템플릿 선택', step: 2 },
  { title: '데이터 확인', step: 3 },
  { title: '컬럼 매핑', step: 4 },
  { title: '정규화 및 생성', step: 5 },
  { title: '결과 확인', step: 6 },
]
</script>

<template>
  <div class="wizard-steps-container">
    <el-steps :active="activeStep - 1" finish-status="success" align-center>
      <el-step v-for="s in steps" :key="s.step" :title="s.title" />
    </el-steps>
  </div>
</template>

<style scoped>
.wizard-steps-container {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
</style>
