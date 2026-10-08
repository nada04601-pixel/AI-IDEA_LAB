#!/usr/bin/env node
// 사용법: node scripts/check.mjs <URL> [--include 수영,결원] [--exclude 마감] [--state state.json] [--file page.html]
//  --state 없이 실행하면 인식한 목록만 보여준다 (인식 테스트용).
//  --file 을 주면 URL 대신 저장된 HTML로 테스트한다 (URL은 링크 기준 주소로만 쓴다).

import { readFile, writeFile } from 'node:fs/promises'
import { extractPosts, diffPosts, matchKeywords } from '../src/board.js'

const args = process.argv.slice(2)
const url = args.find((a) => !a.startsWith('--') && !args[args.indexOf(a) - 1]?.startsWith('--'))
const opt = (name) => { const i = args.indexOf(`--${name}`); return i === -1 ? null : args[i + 1] }
const list = (v) => (v ? v.split(',').map((s) => s.trim()).filter(Boolean) : [])

if (!url) {
  console.error('URL을 입력하세요. 예: node scripts/check.mjs https://example.go.kr/board --include 수영')
  process.exit(2)
}

async function load() {
  if (opt('file')) return readFile(opt('file'), 'utf8')
  const res = await fetch(url, { headers: { 'User-Agent': 'NewPostAlert/0.1 (+https://github.com/nada04601-pixel/AI-IDEA_LAB)' } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  const charset = (res.headers.get('content-type') ?? '').match(/charset=([\w-]+)/i)?.[1]
    ?? buf.subarray(0, 2048).toString('latin1').match(/charset=["']?([\w-]+)/i)?.[1] ?? 'utf-8'
  return new TextDecoder(charset.toLowerCase() === 'ks_c_5601-1987' ? 'euc-kr' : charset).decode(buf)
}

const html = await load()
const { posts, iframes } = extractPosts(html, url)
const filter = { include: list(opt('include')), exclude: list(opt('exclude')) }

if (!posts.length) {
  console.log('게시글 목록을 찾지 못했습니다.')
  if (iframes.length) console.log(`iframe 안에 목록이 있을 수 있습니다:\n  ${iframes.join('\n  ')}`)
  process.exit(1)
}

console.log(`인식한 글 ${posts.length}개 (공지 ${posts.filter((p) => p.notice).length}개)`)
for (const p of posts) {
  const mark = matchKeywords(p.title, filter) ? '●' : ' '
  console.log(`${mark} ${p.notice ? '[공지] ' : ''}${p.title}  ${p.date ?? ''}  ${p.number ?? ''}\n     ${p.key}`)
}

const statePath = opt('state')
if (statePath) {
  const prev = await readFile(statePath, 'utf8').then(JSON.parse).catch(() => null)
  const { fresh, state } = diffPosts(posts, prev)
  await writeFile(statePath, JSON.stringify(state, null, 2))
  const hits = fresh.filter((p) => matchKeywords(p.title, filter))
  if (!prev) console.log(`\n기준선 저장 (${posts.length}개). 다음 실행부터 새 글을 알립니다.`)
  else if (!hits.length) console.log(`\n새 글 없음${fresh.length ? ` (키워드 불일치 ${fresh.length}개)` : ''}`)
  else for (const p of hits) console.log(`\n🔔 새 글: ${p.title}\n   ${p.link}`)
}
