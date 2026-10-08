// 분석 로직 (브라우저·Node 공용, 외부 의존성 없음)

// 유튜브 쇼츠 최대 길이 (2024-10부터 3분)
export const SHORTS_MAX_SECONDS = 180;

// ISO 8601 기간 → 초. 예: "PT1M5S" → 65
export function parseDuration(iso) {
  const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(iso || '');
  if (!m) return 0;
  const [, d = 0, h = 0, min = 0, s = 0] = m.map((v) => Number(v || 0));
  return d * 86400 + h * 3600 + min * 60 + s;
}

export function hoursSince(publishedAt, now = Date.now()) {
  return Math.max((now - new Date(publishedAt).getTime()) / 3_600_000, 0);
}

// YouTube API videos.list 응답 항목 → 화면용 객체
export function toVideo(item, now = Date.now()) {
  const st = item.statistics || {};
  const views = Number(st.viewCount || 0);
  const likes = Number(st.likeCount || 0);
  const comments = Number(st.commentCount || 0);
  const hours = hoursSince(item.snippet.publishedAt, now);
  return {
    id: item.id,
    title: item.snippet.title,
    description: item.snippet.description || '',
    channel: item.snippet.channelTitle,
    tags: item.snippet.tags || [],
    thumbnail: item.snippet.thumbnails?.medium?.url || item.snippet.thumbnails?.default?.url || '',
    publishedAt: item.snippet.publishedAt,
    seconds: parseDuration(item.contentDetails?.duration),
    views,
    likes,
    comments,
    hours,
    // 업로드 직후 몇 분 만에 생긴 조회수가 과하게 부풀지 않도록 최소 1시간으로 나눈다
    viewsPerHour: views / Math.max(hours, 1),
    engagement: views ? (likes + comments) / views : 0,
  };
}

export function isShort(video) {
  return video.seconds > 0 && video.seconds <= SHORTS_MAX_SECONDS;
}

export function rankVideos(videos) {
  return [...videos].sort((a, b) => b.viewsPerHour - a.viewsPerHour);
}

// ---- 키워드 추출 ----

const STOPWORDS = new Set([
  'shorts', 'short', 'youtube', 'youtubeshorts', 'shortsvideo', 'viral', 'fyp', 'foryou', 'trending',
  'the', 'and', 'for', 'with', 'you', 'this', 'that', 'my', 'your', 'how', 'what', 'from', 'are', 'is', 'of', 'to', 'in', 'on', 'a',
  '쇼츠', '숏츠', '유튜브', '영상', '오늘', '진짜', '이거', '그냥', '너무', '정말', '완전', '그리고', '하는', '있는', '없는', '이런', '저런',
  '그런', '모든', '우리', '같은', '하기', '해서', '하면', '했다', '합니다', '입니다', '있다', '없다', '근데', '구독', '좋아요', '추천', '반응', '순간', '직접', '처음', '모음', '레전드', '드디어', '결국', '최고',
]);

// 흔한 조사를 떼어 "먹방은", "먹방을"을 "먹방"으로 모은다 (단순 규칙).
// '이·가·도·만'처럼 명사 끝 글자와 자주 겹치는 조사는 빼서 "고양이"가 "고양"이 되지 않게 한다.
const JOSA = ['에서', '으로', '에게', '까지', '부터', '처럼', '보다', '은', '는', '을', '를', '의'];

function stripJosa(word) {
  for (const j of JOSA) {
    if (word.length - j.length >= 2 && word.endsWith(j) && /[가-힣]$/.test(word)) {
      return word.slice(0, -j.length);
    }
  }
  return word;
}

function normalize(word) {
  return word.toLowerCase().replace(/^[#＃]/, '').trim();
}

function usable(word) {
  if (word.length < 2 || word.length > 20) return false;
  if (/^\d+$/.test(word)) return false;
  return !STOPWORDS.has(word);
}

// 영상 하나에서 키워드 집합을 뽑는다. 해시태그·태그는 그대로, 제목은 단어로 쪼갠다.
export function keywordsOf(video) {
  const found = new Set();
  const add = (raw) => {
    const w = normalize(raw);
    if (usable(w)) found.add(w);
  };

  const text = `${video.title} ${video.description}`;
  for (const m of text.matchAll(/[#＃]([\p{L}\p{N}_]+)/gu)) add(m[1]);
  for (const t of video.tags) add(t.replace(/\s+/g, ''));

  const title = video.title.replace(/[#＃][\p{L}\p{N}_]+/gu, ' ');
  for (const token of title.split(/[^\p{L}\p{N}]+/u)) {
    const w = stripJosa(normalize(token));
    if (usable(w)) found.add(w);
  }
  return found;
}

// 급상승 키워드: 여러 떡상 영상에 함께 등장하는 단어일수록, 그 영상들이 빨리 오를수록 높다.
export function rankKeywords(videos, { minCount = 2, limit = 30 } = {}) {
  const map = new Map();
  for (const v of videos) {
    for (const k of keywordsOf(v)) {
      const e = map.get(k) || { keyword: k, count: 0, views: 0, viewsPerHour: 0, videoIds: [] };
      e.count += 1;
      e.views += v.views;
      e.viewsPerHour += v.viewsPerHour;
      e.videoIds.push(v.id);
      map.set(k, e);
    }
  }
  return [...map.values()]
    .filter((e) => e.count >= minCount)
    .map((e) => ({ ...e, score: e.viewsPerHour * Math.sqrt(e.count) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

// ---- 표시용 ----

export function formatCount(n) {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1).replace(/\.0$/, '')}억`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(1).replace(/\.0$/, '')}만`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}천`;
  return String(Math.round(n));
}

export function formatAgo(hours) {
  if (hours < 1) return `${Math.max(Math.round(hours * 60), 1)}분 전`;
  if (hours < 48) return `${Math.floor(hours)}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}
