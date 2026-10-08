// 의존성 없는 관대한 HTML 파서. 게시판 목록을 찾는 데 필요한 만큼만 트리를 만든다.

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'])
const RAW = new Set(['script', 'style', 'textarea', 'noscript'])
// 같은 태그가 다시 열리면 앞의 것을 닫는 태그 (닫는 태그를 빼먹은 HTML 대응)
const AUTO_CLOSE = { li: ['li'], tr: ['tr', 'td', 'th'], td: ['td', 'th'], th: ['td', 'th'], p: ['p'], option: ['option'], dt: ['dt', 'dd'], dd: ['dt', 'dd'] }

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', middot: '·' }

export function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') {
      const code = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)
      return Number.isFinite(code) ? String.fromCodePoint(code) : m
    }
    return ENTITIES[e.toLowerCase()] ?? m
  })
}

function parseAttrs(src) {
  const attrs = {}
  const re = /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g
  let m
  while ((m = re.exec(src))) attrs[m[1].toLowerCase()] = decodeEntities(m[2] ?? m[3] ?? m[4] ?? '')
  return attrs
}

export function parseHtml(html) {
  const root = { tag: '#root', attrs: {}, children: [], parent: null }
  const stack = [root]
  const top = () => stack[stack.length - 1]
  const re = /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<![^>]*>|<\/\s*([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:"[^"]*"|'[^']*'|[^'">])*)>|([^<]+|<)/g
  let m
  while ((m = re.exec(html))) {
    if (m[4] !== undefined) {
      top().children.push({ text: decodeEntities(m[4]), parent: top() })
    } else if (m[2]) {
      const tag = m[2].toLowerCase()
      const closes = AUTO_CLOSE[tag]
      if (closes) {
        // 가장 가까운 table/ul 경계 안에서만 자동으로 닫는다
        for (let i = stack.length - 1; i > 0; i--) {
          const t = stack[i].tag
          if (closes.includes(t)) { stack.length = i; break }
          if (['table', 'tbody', 'thead', 'ul', 'ol', 'dl', 'select', 'div'].includes(t)) break
        }
      }
      const node = { tag, attrs: parseAttrs(m[3]), children: [], parent: top() }
      top().children.push(node)
      const selfClosing = /\/\s*$/.test(m[3])
      if (RAW.has(tag) && !selfClosing) {
        const end = html.toLowerCase().indexOf(`</${tag}`, re.lastIndex)
        const stop = end === -1 ? html.length : end
        node.children.push({ text: html.slice(re.lastIndex, stop), parent: node, raw: true })
        re.lastIndex = stop
      } else if (!VOID.has(tag) && !selfClosing) {
        stack.push(node)
      }
    } else if (m[1]) {
      const tag = m[1].toLowerCase()
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tag === tag) { stack.length = i; break }
      }
    }
  }
  return root
}

export function* walk(node) {
  for (const c of node.children ?? []) {
    if (c.tag) { yield c; yield* walk(c) }
  }
}

export function textOf(node) {
  if (node.text !== undefined) return node.raw ? '' : node.text
  if (node.tag === 'img') return node.attrs.alt ? ` ${node.attrs.alt} ` : ''
  return (node.children ?? []).map(textOf).join(' ')
}

export const clean = (s) => s.replace(/\s+/g, ' ').trim()
