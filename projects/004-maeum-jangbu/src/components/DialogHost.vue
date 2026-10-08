<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { dialog } from '../lib/dialog'
import { onBack } from '../lib/back'

// 확인 창이 열려 있으면 뒤로가기는 "취소"(취소 버튼이 없는 질문은 그대로 둠)
const off = onBack(() => {
  const d = dialog.value
  if (!d) return false
  const cancel = d.buttons.find((b) => b.cancel)
  if (cancel) d.resolve(cancel.value)
  return true
})
onBeforeUnmount(off)
</script>

<template>
  <Teleport to="body">
    <div v-if="dialog" class="backdrop" role="alertdialog" :aria-label="dialog.title">
      <div class="box">
        <h2>{{ dialog.title }}</h2>
        <p class="msg">{{ dialog.message }}</p>
        <div class="btns">
          <button
            v-for="(b, i) in dialog.buttons"
            :key="i"
            class="btn"
            :class="{ secondary: !b.primary }"
            @click="dialog.resolve(b.value)"
          >{{ b.label }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.4); z-index: 70; display: grid; place-items: center; padding: 20px; }
.box { width: 100%; max-width: 400px; background: var(--surface); border-radius: 18px; padding: 22px 18px 18px; }
.box h2 { font-size: 1.1rem; }
.msg { white-space: pre-line; color: var(--text-2); margin: 8px 0 18px; }
.btns { display: flex; gap: 8px; }
.btns .btn { flex: 1; }
</style>
