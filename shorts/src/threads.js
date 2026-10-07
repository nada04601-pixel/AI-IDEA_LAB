// Threads API 키워드 검색으로 최근 인기 영상 게시물을 찾는다 (수집 스크립트 전용).
// 공개 게시물을 검색하려면 앱에 threads_keyword_search 권한 승인이 필요하다 (승인 전에는 내 게시물만 나온다).
// 한도: 사용자당 24시간에 검색 2,200회. 공개 게시물의 조회수·좋아요는 API가 주지 않아 Threads의 인기순(TOP)을 그대로 쓴다.

const BASE = 'https://graph.threads.net/v1.0';
const FIELDS = 'id,text,media_type,permalink,timestamp,username,thumbnail_url';

// 검색어별 인기순으로 영상 게시물을 가져와 하나로 합친다.
// 여러 검색어에서 높은 순위로 나온 게시물일수록 앞에 온다.
export async function searchThreadsVideos({ accessToken, queries, hours = 24, now = Date.now() }, fetchImpl = fetch) {
  const since = Math.floor((now - hours * 3_600_000) / 1000);
  const map = new Map();
  for (const q of queries) {
    const params = { q, search_type: 'TOP', media_type: 'VIDEO', since, fields: FIELDS, access_token: accessToken };
    const res = await fetchImpl(`${BASE}/keyword_search?${new URLSearchParams(params)}`);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(explain(body.error, res.status));
      err.reason = body.error?.code === 190 ? 'keyInvalid' : body.error?.code === 4 || body.error?.code === 613 ? 'quotaExceeded' : '';
      throw err;
    }
    (body.data || []).forEach((post, i) => {
      if (post.media_type && post.media_type !== 'VIDEO') return;
      const e = map.get(post.id) || { post, query: q, score: 0 };
      e.score += 1 / (i + 1);
      map.set(post.id, e);
    });
  }
  return [...map.values()].sort((a, b) => b.score - a.score).map((e) => ({ ...e.post, query: e.query, score: e.score }));
}

function explain(error, status) {
  if (error?.code === 190) return '스레드 액세스 토큰이 만료됐거나 올바르지 않아요. 토큰을 새로 발급해 THREADS_ACCESS_TOKEN 시크릿을 바꿔 주세요.';
  if (error?.code === 4 || error?.code === 613) return '스레드 검색 한도(24시간 2,200회)를 넘었어요.';
  return `Threads API 오류: ${error?.message || `HTTP ${status}`}`;
}
