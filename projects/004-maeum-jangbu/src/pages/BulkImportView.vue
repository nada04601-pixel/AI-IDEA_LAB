<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { shareFile } from '../lib/share'
import { templateCsv } from '../lib/sheet'
import { isSheetFile, readSheetFile } from '../lib/sheetFile'
import { pendingImport } from '../lib/pendingImport'
import { isNativeApp } from '../lib/platform'
import { showToast } from '../lib/toast'

/**
 * 엑셀·CSV로 한꺼번에 등록 (2026-10-08 추가)
 * ① 빈 양식 받기 → ② 채우기 → ③ 올리기 → 가져오기 화면에서 미리보기·확인 후 등록
 */
const router = useRouter()
const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref<'xlsx' | 'csv' | 'read' | null>(null)
const error = ref<string | null>(null)

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

async function getTemplate(kind: 'xlsx' | 'csv') {
  busy.value = kind
  error.value = null
  try {
    const res =
      kind === 'xlsx'
        ? await shareFile('마음장부_일괄등록_양식.xlsx', await (await import('../lib/excel')).buildTemplate(), XLSX_MIME, '마음장부 엑셀 양식')
        : await shareFile('마음장부_일괄등록_양식.csv', templateCsv(), 'text/csv', '마음장부 CSV 양식')
    if (res === 'shared') showToast(isNativeApp ? '양식을 저장할 곳에 보냈어요' : '양식을 내려받았어요', 2400)
  } catch (e) {
    error.value = `양식을 만들지 못했어요. (${(e as Error).message})`
  } finally {
    busy.value = null
  }
}

async function onFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  if (!f) return
  error.value = null
  if (!isSheetFile(f.name)) {
    error.value = '엑셀(.xlsx) 또는 CSV(.csv) 파일을 골라 주세요. 구글 시트는 [다운로드 → Microsoft Excel]로 저장한 파일을 쓰세요.'
    return
  }
  busy.value = 'read'
  try {
    pendingImport.value = { fileName: f.name, result: await readSheetFile(f) }
    router.push('/restore?from=bulk')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div class="page no-tab">
    <p class="lead">명단이 많으면 엑셀이나 구글 시트로 정리해서 한 번에 올리세요.</p>

    <section class="card step">
      <h2><span class="no">1</span> 빈 양식 받기</h2>
      <div class="btn-row">
        <button class="btn secondary" :disabled="!!busy" @click="getTemplate('xlsx')">{{ busy === 'xlsx' ? '만드는 중…' : '📊 엑셀 양식' }}</button>
        <button class="btn secondary" :disabled="!!busy" @click="getTemplate('csv')">{{ busy === 'csv' ? '만드는 중…' : '📄 CSV 양식' }}</button>
      </div>
      <p class="muted small">엑셀 양식에는 고르기 목록(받음/보냄, 관계, 방식)과 "작성 방법" 시트가 들어 있어요. {{ isNativeApp ? '카카오톡 나에게·드라이브로 보내 PC에서 열면 편해요.' : '' }}</p>
    </section>

    <section class="card step">
      <h2><span class="no">2</span> 한 줄에 한 사람씩 채우기</h2>
      <table class="rules small">
        <tbody>
          <tr><th>필수</th><td><strong>날짜 · 이름 · 금액</strong></td></tr>
          <tr><th>날짜</th><td>2024-05-18, 2024.05.18, 2024년 5월 18일</td></tr>
          <tr><th>금액</th><td>100000, 100,000, 10만, 10만원 · 화환·선물은 0</td></tr>
          <tr><th>받음/보냄</th><td>비우면 받음. 보낸 돈은 "보냄" (그 사람의 경조사로 등록)</td></tr>
          <tr><th>행사</th><td>같은 날짜·같은 행사 이름은 한 행사로 묶여요. 비우면 종류로 이름을 붙여요</td></tr>
          <tr><th>나머지</th><td>행사 종류·관계·소속·방식·참석·감사 인사·메모는 비워도 돼요</td></tr>
        </tbody>
      </table>
      <p class="muted small">"축의금", "성명", "일자"처럼 열 이름이 조금 달라도 알아봐요.</p>
    </section>

    <section class="card step">
      <h2><span class="no">3</span> 파일 올리기</h2>
      <button class="btn" :disabled="!!busy" @click="fileInput?.click()">{{ busy === 'read' ? '읽는 중…' : '채운 파일 올리기' }}</button>
      <!-- 안드로이드 파일 선택기는 MIME으로 xlsx를 못 알아보는 경우가 있어 앱에서는 제한하지 않는다 -->
      <input ref="fileInput" type="file" hidden :accept="isNativeApp ? undefined : '.xlsx,.csv,text/csv'" @change="onFile" />
      <p class="muted small">다음 화면에서 몇 명·몇 건인지, 이미 있는 기록(중복)은 몇 건인지 먼저 보여 드려요. 확인한 뒤에 등록돼요.</p>
      <p class="muted small">구글 시트는 [파일 → 다운로드 → Microsoft Excel(.xlsx)]로 저장한 파일을 올리세요.</p>
    </section>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.lead { margin: 0 0 14px; }
.step { margin-bottom: 12px; display: flex; flex-direction: column; gap: 10px; }
.step h2 { margin: 0; display: flex; align-items: center; gap: 8px; }
.step p { margin: 0; }
.no { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: var(--accent-text); font-size: 0.8rem; }
.rules { width: 100%; border-collapse: collapse; }
.rules th { text-align: left; white-space: nowrap; color: var(--text-2); font-weight: 600; padding: 5px 10px 5px 0; vertical-align: top; }
.rules td { padding: 5px 0; }
.rules tr + tr { border-top: 1px solid var(--line); }
.error { color: var(--warn); background: var(--warn-soft); padding: 10px 12px; border-radius: 10px; }
</style>
