import { getSetting, setSetting } from './db'

export type FontSize = 'normal' | 'large' | 'xlarge'

export async function applyFontSize(size?: FontSize) {
  const s = size ?? (await getSetting<FontSize>('fontSize', 'normal'))
  document.documentElement.dataset.font = s
}

export async function setFontSize(size: FontSize) {
  await setSetting('fontSize', size)
  await applyFontSize(size)
}
