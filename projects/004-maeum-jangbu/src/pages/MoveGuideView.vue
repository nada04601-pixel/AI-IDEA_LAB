<template>
  <div class="page no-tab">
    <h1>새 휴대폰으로 옮기기</h1>
    <p class="muted">마음장부는 서버가 없어서 백업 파일로 옮겨요.</p>
    <ol class="steps">
      <li class="card"><strong>지금 휴대폰에서 백업 파일 만들기</strong><br /><span class="muted small">카카오톡 나에게 보내기나 구글 드라이브에 저장해 두세요.</span>
        <RouterLink to="/backup" class="btn sm step-btn">백업하러 가기</RouterLink>
      </li>
      <li class="card"><strong>새 휴대폰에 마음장부 설치</strong></li>
      <li class="card"><strong>새 휴대폰에서 백업 파일 가져오기</strong><br /><span class="muted small">설정 → 가져오기·복원 → 저장해 둔 파일 선택</span></li>
      <li class="card"><strong>기록이 잘 보이는지 확인한 뒤에</strong> 예전 휴대폰의 앱을 지우세요.</li>
    </ol>
  </div>
</template>

<style scoped>
.steps { padding-left: 22px; display: flex; flex-direction: column; gap: 10px; margin-top: 18px; }
.steps li::marker { font-weight: 800; color: var(--accent); }
.step-btn { margin-top: 10px; }
</style>
