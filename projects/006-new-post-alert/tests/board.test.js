import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { extractPosts, diffPosts, matchKeywords } from '../src/board.js'

const fixture = (name) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8')
const BASE = 'https://example.go.kr/public/html/sub04/040102.html'

test('표 게시판: 메뉴·꼬리말·페이지 링크를 빼고 글 목록만 찾는다', () => {
  const { posts } = extractPosts(fixture('table-board.html'), BASE)
  assert.deepEqual(posts.map((p) => p.title), [
    '2026년 하반기 체육시설 이용 안내',
    '국민체육센터 수영 강습 결원 추가모집 안내',
    '2026년 10월 정기 민방위 교육 실시 알림',
    '딸기축제 자원봉사자 모집 공고',
    '수영장 정기 휴장 안내 (10월)',
  ])
  assert.equal(posts[0].notice, true)
  assert.equal(posts[1].notice, false)
  assert.equal(posts[1].number, '1532')
  assert.equal(posts[1].date, '2026-10-07')
})

test('글 키에서 페이지 번호를 뺀다 (2쪽에서 봐도 같은 글)', () => {
  const p1 = extractPosts(fixture('table-board.html'), BASE).posts
  const p2 = extractPosts(fixture('table-board.html').replaceAll('pageIndex=1', 'pageIndex=2'), BASE).posts
  assert.deepEqual(p1.map((p) => p.key), p2.map((p) => p.key))
  assert.equal(p1[1].key, 'url:https://example.go.kr/public/html/sub04/040102.html?idx=1532&mode=view')
})

test('자바스크립트 링크 게시판: 함수 인자로 글을 구분한다', () => {
  const { posts } = extractPosts(fixture('js-board.html'), BASE)
  assert.equal(posts.length, 3)
  assert.deepEqual(posts.map((p) => p.key), ['js:20261008001', 'js:20261007003', 'js:20261006002'])
  assert.equal(posts[2].date, '2026.10.06')
})

test('첫 실행은 기준선만, 이후엔 처음 보는 글만 새 글', () => {
  const html = fixture('table-board.html')
  const first = diffPosts(extractPosts(html, BASE).posts, null)
  assert.equal(first.fresh.length, 0)

  // 새 글 1개가 위에 붙고 맨 아래 글은 다음 쪽으로 밀려남, 공지 순서도 그대로
  const next = html
    .replace('<tr><td>1532</td>', '<tr><td>1533</td><td class="subject"><a href="040102.html?mode=view&amp;idx=1533&amp;pageIndex=1">실내수영장 새벽반 결원 접수 안내</a></td><td>시설관리사업소</td><td>2026-10-08</td></tr>\n<tr><td>1532</td>')
    .replace(/<tr><td>1529<\/td>.*<\/tr>/, '')
  const second = diffPosts(extractPosts(next, BASE).posts, first.state)
  assert.deepEqual(second.fresh.map((p) => p.title), ['실내수영장 새벽반 결원 접수 안내'])

  // 같은 페이지를 다시 보면 새 글 없음
  assert.equal(diffPosts(extractPosts(next, BASE).posts, second.state).fresh.length, 0)
})

test('제목 수정은 새 글이 아니다', () => {
  const html = fixture('table-board.html')
  const { state } = diffPosts(extractPosts(html, BASE).posts, null)
  const edited = html.replace('딸기축제 자원봉사자 모집 공고', '[수정] 딸기축제 자원봉사자 모집 공고')
  assert.equal(diffPosts(extractPosts(edited, BASE).posts, state).fresh.length, 0)
})

test('키워드: 포함 중 하나 + 제외 우선, 띄어쓰기 무시', () => {
  const f = { include: ['수영', '결원'], exclude: ['휴장'] }
  assert.equal(matchKeywords('국민체육센터 수영 강습 결원 추가모집 안내', f), true)
  assert.equal(matchKeywords('수영장 정기 휴장 안내', f), false)
  assert.equal(matchKeywords('민방위 교육', f), false)
  assert.equal(matchKeywords('실내 수 영 강습', { include: ['수영'] }), true)
  assert.equal(matchKeywords('아무 글', {}), true)
})
