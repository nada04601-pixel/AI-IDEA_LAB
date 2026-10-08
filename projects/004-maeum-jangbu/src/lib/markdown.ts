/**
 * 개인정보처리방침처럼 앱에 넣는 간단한 문서용 마크다운 → HTML (외부 라이브러리 없이)
 * 지원: # / ## / ### 제목, - 목록, 문단, **굵게**. 모든 글자는 HTML 이스케이프한다.
 */
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const inline = (s: string) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

export function renderMarkdown(md: string): string {
  const out: string[] = []
  let list: string[] | null = null
  let para: string[] = []
  const flush = () => {
    if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`)
    para = []
    if (list) out.push(`<ul>${list.map((li) => `<li>${inline(li)}</li>`).join('')}</ul>`)
    list = null
  }
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trimEnd()
    const h = /^(#{1,3})\s+(.*)$/.exec(line)
    const li = /^\s*-\s+(.*)$/.exec(line)
    if (h) {
      flush()
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)
    } else if (li) {
      if (para.length) flush()
      ;(list ??= []).push(li[1])
    } else if (!line.trim()) {
      flush()
    } else {
      if (list) flush()
      para.push(line.trim())
    }
  }
  flush()
  return out.join('\n')
}
