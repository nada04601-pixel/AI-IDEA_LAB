// 자동 수집 결과(data/latest.json)를 만드는 로직. 수집 스크립트와 테스트가 함께 쓴다.
import { toVideo, isShort, isKorean, isJapanese, rankVideos, rankKeywords, KOREAN_BROAD_QUERY } from './trend.js';

export const SNAPSHOT_VERSION = 1;
export const KEEP_VIDEOS = 100;

// 탭 묶음. 'platforms'는 수집 데이터가 없는 안내 탭이다 (public.js에서 그린다).
export const GROUPS = [
  { key: 'kr', label: '🇰🇷 한국' },
  { key: 'world', label: '🌏 해외' },
  { key: 'platforms', label: '📱 다른 플랫폼' },
];

// '한국 전체'는 매시간, 나머지(분야·해외)는 한 시간에 하나씩 돌아가며 갱신한다 (할당량 절약).
// q의 '|'는 YouTube 검색의 OR 연산자다.
// regionCode: 검색 국가 ('' = 국가 제한 없음), only: 이 문자가 있는 영상만 남긴다 (ko 한글, ja 가나)
const KR = { group: 'kr', regionCode: 'KR', only: 'ko' };
export const SECTIONS = [
  { key: 'all', label: '전체', query: KOREAN_BROAD_QUERY, ...KR },
  { key: 'food', label: '먹방·요리', query: '먹방|요리|레시피', ...KR },
  { key: 'game', label: '게임', query: '게임|롤|마인크래프트|배그', ...KR },
  { key: 'sports', label: '스포츠', query: '축구|야구|농구|배구', ...KR },
  { key: 'animal', label: '동물', query: '강아지|고양이|댕댕이|냥이', ...KR },
  { key: 'music', label: '아이돌·음악', query: '아이돌|케이팝|챌린지|커버', ...KR },
  { key: 'beauty', label: '뷰티·패션', query: '메이크업|화장|코디|패션', ...KR },
  { key: 'fun', label: '웃긴 영상', query: '웃긴|개그|밈|몰카', ...KR },
  { key: 'us', label: '🇺🇸 미국', query: '', group: 'world', regionCode: 'US' },
  { key: 'jp', label: '🇯🇵 일본', query: '', group: 'world', regionCode: 'JP', only: 'ja' },
  { key: 'global', label: '🌍 전세계', query: '', group: 'world', regionCode: '' },
];

const ONLY = { ko: isKorean, ja: isJapanese };

// 이번 시간에 갱신할 섹션: 한국 전체 + 나머지 중 하나
export function sectionsForRun(date = new Date()) {
  const rotating = SECTIONS.filter((s) => s.key !== 'all');
  const hourIndex = Math.floor(date.getTime() / 3_600_000);
  return [SECTIONS[0], rotating[hourIndex % rotating.length]];
}

function slim(v) {
  return {
    id: v.id,
    title: v.title,
    channel: v.channel,
    thumbnail: v.thumbnail,
    publishedAt: v.publishedAt,
    seconds: v.seconds,
    views: v.views,
    likes: v.likes,
    comments: v.comments,
    viewsPerHour: Math.round(v.viewsPerHour),
    ...(v.recentPerHour != null ? { recentPerHour: v.recentPerHour } : {}),
  };
}

// API 응답(videos.list items) → 섹션. 지난 수집에도 있던 영상은 "그 사이 시간당 증가량"을 붙인다.
// section.only가 있으면 그 언어 영상만 남긴다 (regionCode는 "그 나라에서 볼 수 있는 영상"일 뿐이라)
export function buildSection(section, items, { prev, now = Date.now(), hours }) {
  const all = items.map((it) => toVideo(it, now)).filter(isShort);
  const keep = ONLY[section.only];
  const videos = rankVideos(keep ? all.filter(keep) : all).slice(0, KEEP_VIDEOS);
  const prevAt = prev ? Date.parse(prev.updatedAt) : NaN;
  const gapHours = (now - prevAt) / 3_600_000;
  if (gapHours >= 0.5 && gapHours <= 12) {
    const before = new Map(prev.videos.map((v) => [v.id, v.views]));
    for (const v of videos) {
      if (before.has(v.id)) v.recentPerHour = Math.max(Math.round((v.views - before.get(v.id)) / gapHours), 0);
    }
  }
  const keywords = rankKeywords(videos, { minCount: videos.length >= 40 ? 3 : 2 }).map((k) => ({
    keyword: k.keyword,
    count: k.count,
    views: k.views,
    viewsPerHour: Math.round(k.viewsPerHour),
    videoIds: k.videoIds,
  }));
  return {
    label: section.label,
    group: section.group || 'kr',
    regionCode: section.regionCode ?? 'KR',
    query: section.query,
    hours,
    updatedAt: new Date(now).toISOString(),
    videos: videos.map(slim),
    keywords,
  };
}

// 이번에 갱신한 섹션만 바꾸고 나머지는 지난 결과를 유지한다. 순서는 SECTIONS를 따른다.
export function mergeSnapshot(prev, updated, { now = Date.now(), regionCode, errors = [] } = {}) {
  const old = prev?.version === SNAPSHOT_VERSION ? prev.sections : {};
  const sections = {};
  for (const s of SECTIONS) {
    const sec = updated[s.key] || old[s.key];
    if (sec) sections[s.key] = sec;
  }
  return {
    version: SNAPSHOT_VERSION,
    generatedAt: new Date(now).toISOString(),
    regionCode,
    errors,
    sections,
  };
}
