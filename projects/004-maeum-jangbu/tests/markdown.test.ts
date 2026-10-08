import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { renderMarkdown } from '../src/lib/markdown'

describe('문서 렌더링', () => {
  it('제목·목록·문단·굵게, HTML은 이스케이프', () => {
    expect(renderMarkdown('# 제목\n\n문단 **굵게**\n이어짐\n\n- 하나\n- <b>둘</b>\n## 소제목')).toBe(
      '<h1>제목</h1>\n<p>문단 <strong>굵게</strong> 이어짐</p>\n<ul><li>하나</li><li>&lt;b&gt;둘&lt;/b&gt;</li></ul>\n<h2>소제목</h2>',
    )
  })

  it('개인정보처리방침의 핵심 약속이 들어 있다', () => {
    const md = readFileSync(new URL('../PRIVACY.md', import.meta.url), 'utf8')
    const html = renderMarkdown(md)
    expect(html).toContain('인터넷에 연결하지 않으며')
    expect(html).toContain('전화번호, 이메일, 주소 등 다른 연락처 정보는 읽지 않습니다.')
    expect(html).toContain('구글 계정 자동 백업(클라우드)에는 앱 데이터를 포함하지 않습니다.')
    expect(html).not.toContain('<script')
  })
})
