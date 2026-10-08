// 자동 수집 결과(data/latest.json)를 만드는 로직. 수집 스크립트와 테스트가 함께 쓴다.
import { toVideo, isShort, rankVideos, rankKeywords } from './trend.js';

export const SNAPSHOT_VERSION = 1;
export const KEEP_VIDEOS = 100;

// '전체'는 매시간, 분야는 한 시간에 하나씩 돌아가며 갱신한다 (할당량 절약).
// q의 '|'는 YouTube 검색의 OR 연산자다.
export const SECTIONS = [
  { key: 'all', label: '전체', query: '' },
  { key: 'food', label: '먹방·요리', query: '먹방|요리|레시피' },
  { key: 'game', label: '게임', query: '게임|롤|마인크래프트|배그' },
  { key: 'sports', label: '스포츠', query: '축구|야구|농구|배구' },
  { key: 'animal', label: '동물', query: '강아지|고양이|댕댕이|냥이' },
  { key: 'music', label: '아이돌·음악', query: '아이돌|케이팝|챌린지|커버' },
  { key: 'beauty', label: '뷰티·패션', query: '메이크업|화장|코디|패션' },
  { key: 'fun', label: '웃긴 영상', query: '웃긴|개그|밈|몰카' },
];

// 이번 시간에 갱신할 섹션: 전체 + 분야 하나
export function sectionsForRun(date = new Date()) {
  const categories = SECTIONS.filter((s) => s.key !== 'all');
  const hourIndex = Math.floor(date.getTime() / 3_600_000);
  return [SECTIONS[0], categories[hourIndex % categories.length]];
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
export function buildSection(section, items, { prev, now = Date.now(), hours }) {
  const videos = rankVideos(items.map((it) => toVideo(it, now)).filter(isShort)).slice(0, KEEP_VIDEOS);
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
