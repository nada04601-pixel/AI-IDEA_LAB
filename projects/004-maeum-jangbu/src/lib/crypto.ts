/**
 * 백업 비밀번호 암호화 (tech-stack.md 5-1)
 * 브라우저 내장 Web Crypto만 사용: PBKDF2(SHA-256) → AES-GCM 256.
 * 비밀번호는 어디에도 저장하지 않는다.
 */
export const KDF_ITERATIONS = 600_000

export interface EncryptedPayload {
  kdf: { name: 'PBKDF2'; hash: 'SHA-256'; iterations: number; salt: string }
  cipher: { name: 'AES-GCM'; iv: string }
  data: string
}

export class WrongPasswordError extends Error {
  constructor() {
    super('비밀번호가 맞지 않아요.')
  }
}

const enc = new TextEncoder()
const dec = new TextDecoder()

export function toBase64(bytes: Uint8Array): string {
  let bin = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) bin += String.fromCharCode(...bytes.subarray(i, i + chunk))
  return btoa(bin)
}

export function fromBase64(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

async function deriveKey(password: string, salt: Uint8Array<ArrayBuffer>, iterations: number) {
  const base = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export async function encryptText(plain: string, password: string, iterations = KDF_ITERATIONS): Promise<EncryptedPayload> {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt, iterations)
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(plain)))
  return {
    kdf: { name: 'PBKDF2', hash: 'SHA-256', iterations, salt: toBase64(salt) },
    cipher: { name: 'AES-GCM', iv: toBase64(iv) },
    data: toBase64(cipher),
  }
}

/** 비밀번호가 틀리면 WrongPasswordError (AES-GCM 인증 실패) */
export async function decryptText(payload: EncryptedPayload, password: string): Promise<string> {
  const key = await deriveKey(password, fromBase64(payload.kdf.salt), payload.kdf.iterations)
  try {
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromBase64(payload.cipher.iv) }, key, fromBase64(payload.data))
    return dec.decode(plain)
  } catch {
    throw new WrongPasswordError()
  }
}
