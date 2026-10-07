import { registerPlugin } from '@capacitor/core'
import { isNativeApp } from './platform'
import type { PhoneContact } from './contactsImport'

/** android/.../ContactReaderPlugin.java — 읽기 전용, 이름·회사명만 */
interface ContactReaderPlugin {
  pick(): Promise<{ canceled: boolean; name?: string }>
  list(): Promise<{ contacts: PhoneContact[] }>
}
const native = registerPlugin<ContactReaderPlugin>('ContactReader')

/** 브라우저 개발 서버(npm run dev)에서 화면을 확인하기 위한 가짜 연락처. 앱·배포 빌드에서는 쓰지 않는다 */
const devMock: ContactReaderPlugin = {
  pick: async () => ({ canceled: false, name: '한지민' }),
  list: async () => ({
    contacts: [
      { id: '1', name: '김민수', org: '' }, { id: '2', name: '한지민', org: '○○회사' }, { id: '3', name: '오정훈', org: '△△은행' },
      { id: '4', name: '오정훈', org: '△△은행' }, { id: '5', name: '  박 지영 ', org: '' }, { id: '6', name: '최서연', org: '' },
    ],
  }),
}
const useMock = !isNativeApp && import.meta.env.DEV
const ContactReader = useMock ? devMock : native

/** 연락처는 안드로이드 앱에서만 */
export const contactsSupported = isNativeApp || useMock

/** 연락처에서 1명 고르기 (권한 필요 없음). 취소하면 null */
export async function pickContactName(): Promise<string | null> {
  const r = await ContactReader.pick()
  return r.canceled || !r.name ? null : r.name
}

export class ContactsDeniedError extends Error {
  constructor() {
    super('연락처 권한을 허용하지 않았어요. 휴대폰 설정 → 애플리케이션 → 마음장부 → 권한에서 바꿀 수 있어요.')
  }
}

/** 연락처 전체 (이름·회사명). 이때만 읽기 권한을 요청한다 */
export async function listContacts(): Promise<PhoneContact[]> {
  try {
    return (await ContactReader.list()).contacts
  } catch (e) {
    const err = e as { code?: string; message?: string }
    if (err.code === 'DENIED' || /권한|permission/i.test(err.message ?? '')) throw new ContactsDeniedError()
    throw e
  }
}
