import { shallowRef } from 'vue'

export interface DialogButton<T> {
  label: string
  value: T
  primary?: boolean
}

export interface DialogState {
  title: string
  message: string
  buttons: DialogButton<unknown>[]
  resolve: (v: unknown) => void
}

export const dialog = shallowRef<DialogState | null>(null)

/** 버튼 여러 개를 고를 수 있는 확인 창. 바깥을 누르면 cancelValue */
export function ask<T>(title: string, message: string, buttons: DialogButton<T>[]): Promise<T> {
  return new Promise((resolve) => {
    dialog.value = {
      title,
      message,
      buttons: buttons as DialogButton<unknown>[],
      resolve: (v) => {
        dialog.value = null
        resolve(v as T)
      },
    }
  })
}

export const confirmAsk = (title: string, message: string, ok = '확인', cancel = '취소') =>
  ask(title, message, [
    { label: cancel, value: false },
    { label: ok, value: true, primary: true },
  ])
