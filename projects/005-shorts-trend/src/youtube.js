// YouTube Data API v3 호출 (사용자 본인의 API 키 사용)
// 할당량: search.list = 페이지당 100단위, videos.list = 호출당 1단위 (기본 하루 10,000단위)

const BASE = 'https://www.googleapis.com/youtube/v3';

async function call(path, params, fetchImpl) {
  const url = `${BASE}/${path}?${new URLSearchParams(params)}`;
  const res = await fetchImpl(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = body.error?.message || `HTTP ${res.status}`;
    // 잘못된 키는 reason이 'badRequest'로 와서 메시지로 구분한다
    const reason = /API key not valid/i.test(message) ? 'keyInvalid' : body.error?.errors?.[0]?.reason || '';
    const err = new Error(explain(reason, message));
    err.reason = reason;
    throw err;
  }
  return body;
}

function explain(reason, message) {
  if (reason === 'quotaExceeded') return '오늘 API 할당량을 다 썼어요. 한국 시간 오후 4~5시(태평양 자정)에 초기화됩니다.';
  if (reason === 'keyInvalid') return 'API 키가 올바르지 않아요. 키를 다시 확인해 주세요.';
  if (reason === 'accessNotConfigured') return '이 키의 프로젝트에서 YouTube Data API v3가 사용 설정되지 않았어요.';
  return `YouTube API 오류: ${message}`;
}

// 최근 N시간 안에 올라온 짧은 영상(4분 미만)을 조회수 순으로 찾는다.
export async function searchRecentShortIds(
  { apiKey, regionCode = 'KR', hours = 24, query = '', pages = 1 },
  fetchImpl = fetch,
) {
  const publishedAfter = new Date(Date.now() - hours * 3_600_000).toISOString();
  const lang = { KR: 'ko', JP: 'ja', US: 'en', GB: 'en', TW: 'zh-Hant', VN: 'vi', ID: 'id' }[regionCode];
  const ids = [];
  let pageToken = '';
  let quota = 0;
  for (let i = 0; i < pages; i++) {
    const params = {
      key: apiKey,
      part: 'id',
      type: 'video',
      videoDuration: 'short',
      order: 'viewCount',
      maxResults: '50',
      regionCode,
      publishedAfter,
    };
    if (lang) params.relevanceLanguage = lang;
    if (query) params.q = query;
    if (pageToken) params.pageToken = pageToken;
    const body = await call('search', params, fetchImpl);
    quota += 100;
    for (const it of body.items || []) if (it.id?.videoId) ids.push(it.id.videoId);
    pageToken = body.nextPageToken;
    if (!pageToken) break;
  }
  return { ids: [...new Set(ids)], quota };
}

// 영상 상세(조회수·길이·태그)를 50개씩 묶어 가져온다.
export async function fetchVideoDetails({ apiKey, ids }, fetchImpl = fetch) {
  const items = [];
  let quota = 0;
  for (let i = 0; i < ids.length; i += 50) {
    const body = await call(
      'videos',
      { key: apiKey, part: 'snippet,contentDetails,statistics', id: ids.slice(i, i + 50).join(',') },
      fetchImpl,
    );
    quota += 1;
    items.push(...(body.items || []));
  }
  return { items, quota };
}
