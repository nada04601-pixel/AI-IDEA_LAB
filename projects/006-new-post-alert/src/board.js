// 게시판 목록 자동 인식, 새 글 판단, 키워드 필터

import { parseHtml, walk, textOf, clean } from './html.js'

// 메뉴·머리말·꼬리말 영역 (여기 있는 링크 묶음은 게시글 목록이 아니다)
const CHROME = /(^|[\s_-])(gnb|lnb|snb|nav|menu|header|footer|top|util|quick|location|breadcrumb|sitemap|tab|paging|pagination|banner|family)([\s_-]|$)/i
// 페이지·정렬 등 글과 무관하게 바뀌는 쿼리 값
const VOLATILE_PARAMS = /^(page|pageindex|pageno|pagenum|cpage|curpage|currentpage|startpage|pageunit|recordcountperpage|listsize|pagesize|offset|start|sort|order|searchcnd|searchwrd|searchkeyword|searchcondition|jsessionid)$/i
const ROW_TAGS = new Set(['tr', 'li', 'dl', 'article'])
const DATE_RE = /(20\d{2}|\d{2})[.\-/년]\s?(\d{1,2})[.\-/월]\s?(\d{1,2})/

function rowOf(a) {
  for (let n = a.parent; n && n.tag !== '#root'; n = n.parent) {
    if (ROW_TAGS.has(n.tag)) return n
  }
  return a.parent
}

function inChrome(node) {
  for (let n = node; n && n.tag !== '#root'; n = n.parent) {
    if (['nav', 'header', 'footer'].includes(n.tag)) return true
    if (CHROME.test(`${n.attrs.class ?? ''} ${n.attrs.id ?? ''}`)) return true
  }
  return false
}

// 위치에 따라 바뀌지 않는 조상 경로 (같은 목록의 링크는 같은 서명을 갖는다)
function signature(a, row) {
  const parts = []
  for (let n = a; n && n.tag !== '#root'; n = n.parent) {
    // 행 단위 class(공지 강조 등)는 행마다 다를 수 있어 빼고, 셀 class는 넣는다
    const cls = n === row ? '' : (n.attrs.class ?? '').split(/\s+/).filter((c) => c && !/notice|on|active|new|first|last|odd|even|top|fix/i.test(c)).sort().join('.')
    parts.push(cls ? `${n.tag}.${cls}` : n.tag)
  }
  return parts.join('<')
}

function anchorTitle(a) {
  const t = clean(textOf(a))
  return t.length >= 2 ? t : clean(a.attrs.title ?? '')
}

export function findList(root) {
  const groups = new Map()
  for (const a of walk(root)) {
    if (a.tag !== 'a') continue
    const href = a.attrs.href ?? ''
    if (/^(mailto:|tel:)/i.test(href)) continue
    if ((href === '' || href === '#') && !a.attrs.onclick) continue
    const title = anchorTitle(a)
    if (title.length < 4) continue
    const row = rowOf(a)
    const sig = signature(a, row)
    if (!groups.has(sig)) groups.set(sig, [])
    groups.get(sig).push({ a, row, title })
  }
  let best = null
  for (const [sig, items] of groups) {
    // 한 행에 같은 서명 링크가 여러 개면 첫 번째만 쓴다
    const seen = new Set()
    const uniq = items.filter((it) => !seen.has(it.row) && seen.add(it.row))
    if (uniq.length < 3) continue
    const avgLen = uniq.reduce((s, it) => s + it.title.length, 0) / uniq.length
    const dated = uniq.filter((it) => DATE_RE.test(textOf(it.row))).length / uniq.length
    let score = uniq.length * Math.min(avgLen, 40) * (1 + 2 * dated)
    if (uniq[0].row.tag === 'tr') score *= 1.5
    if (inChrome(uniq[0].a)) score *= 0.05
    if (!best || score > best.score) best = { sig, score, items: uniq }
  }
  return best
}

function cellTexts(row) {
  if (row.tag !== 'tr') return []
  return row.children.filter((c) => c.tag === 'td' || c.tag === 'th').map((c) => clean(textOf(c)))
}

function normalizeHref(href, baseUrl) {
  if (!href || href === '#' || /^javascript:/i.test(href)) return null
  try {
    const u = new URL(href, baseUrl)
    u.hash = ''
    for (const k of [...u.searchParams.keys()]) if (VOLATILE_PARAMS.test(k)) u.searchParams.delete(k)
    u.searchParams.sort()
    return u.toString()
  } catch {
    return null
  }
}

// javascript:fnView('123') / onclick="goView(123, 'B01')" 같은 링크에서 글 식별값을 꺼낸다
function scriptArgs(a) {
  const src = `${/^javascript:/i.test(a.attrs.href ?? '') ? a.attrs.href : ''} ${a.attrs.onclick ?? ''}`
  const m = src.match(/\(([^)]*)\)/)
  if (!m) return null
  const args = m[1].split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean)
  return args.length ? args.join('|') : null
}

export function extractPosts(html, baseUrl) {
  const root = parseHtml(html)
  const list = findList(root)
  const iframes = [...walk(root)].filter((n) => n.tag === 'iframe' && n.attrs.src).map((n) => new URL(n.attrs.src, baseUrl).toString())
  if (!list) return { posts: [], iframes }
  const posts = list.items.map(({ a, row, title }) => {
    const rowText = clean(textOf(row))
    const cells = cellTexts(row)
    const date = rowText.match(DATE_RE)
    const number = cells.find((c) => /^\d+$/.test(c)) ?? null
    const notice = /공지|notice/i.test(`${row.attrs.class ?? ''} ${cells[0] ?? ''}`) || /^공지\b/.test(rowText)
    const link = normalizeHref(a.attrs.href, baseUrl)
    const js = scriptArgs(a)
    const key = link ? `url:${link}` : js ? `js:${js}` : number ? `no:${number}` : `t:${title}|${date?.[0] ?? ''}`
    return { key, title, link: link ?? baseUrl, number, date: date ? date[0] : null, notice }
  })
  return { posts, iframes }
}

// 처음 보는 글만 새 글. 첫 실행은 기준선만 저장한다.
export function diffPosts(posts, state) {
  const seen = new Set(state?.seen ?? [])
  const isFirst = !state?.seen
  const fresh = isFirst ? [] : posts.filter((p) => !seen.has(p.key))
  for (const p of posts) seen.add(p.key)
  // 최근 키만 유지 (목록에서 밀려난 글이 다시 나타나도 새 글로 보지 않을 만큼 넉넉히)
  const keep = [...seen].slice(-1000)
  return { fresh, state: { seen: keep, checkedAt: new Date().toISOString() } }
}

export function matchKeywords(title, { include = [], exclude = [] } = {}) {
  const t = title.toLowerCase().replace(/\s+/g, '')
  const has = (k) => t.includes(k.toLowerCase().replace(/\s+/g, ''))
  if (exclude.some(has)) return false
  return include.length === 0 || include.some(has)
}
