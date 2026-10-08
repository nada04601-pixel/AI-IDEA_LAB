import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseDuration, toVideo, isShort, isKorean, rankVideos, keywordsOf, rankKeywords, formatCount, formatAgo } from '../src/trend.js';
import { demoItems } from '../src/demo.js';
import { searchRecentShortIds, fetchVideoDetails } from '../src/youtube.js';

const NOW = Date.parse('2026-10-08T12:00:00Z');

function item({ id = 'a', title = '', hoursAgo = 2, duration = 'PT30S', views = 1000, tags } = {}) {
  return {
    id,
    snippet: { title, description: '', channelTitle: 'ch', publishedAt: new Date(NOW - hoursAgo * 3_600_000).toISOString(), tags },
    contentDetails: { duration },
    statistics: { viewCount: String(views), likeCount: '10', commentCount: '2' },
  };
}

test('parseDuration', () => {
  assert.equal(parseDuration('PT1M5S'), 65);
  assert.equal(parseDuration('PT45S'), 45);
  assert.equal(parseDuration('PT1H'), 3600);
  assert.equal(parseDuration('P0D'), 0);
  assert.equal(parseDuration(undefined), 0);
});

test('시간당 조회수는 최소 1시간으로 나눈다', () => {
  assert.equal(toVideo(item({ hoursAgo: 4, views: 4000 }), NOW).viewsPerHour, 1000);
  assert.equal(toVideo(item({ hoursAgo: 0.1, views: 500 }), NOW).viewsPerHour, 500);
});

test('3분 이하만 쇼츠로 본다', () => {
  assert.equal(isShort(toVideo(item({ duration: 'PT3M' }), NOW)), true);
  assert.equal(isShort(toVideo(item({ duration: 'PT3M1S' }), NOW)), false);
  assert.equal(isShort(toVideo(item({ duration: 'P0D' }), NOW)), false); // 라이브 등
});

test('rankVideos는 시간당 조회수 내림차순', () => {
  const vs = [item({ id: 'slow', hoursAgo: 10, views: 10000 }), item({ id: 'fast', hoursAgo: 1, views: 5000 })].map((i) => toVideo(i, NOW));
  assert.deepEqual(rankVideos(vs).map((v) => v.id), ['fast', 'slow']);
});

test('keywordsOf: 해시태그·태그·제목 단어, 불용어와 조사 처리', () => {
  const k = keywordsOf(toVideo(item({ title: '먹방은 진짜 고양이 #Shorts #편의점', tags: ['자취 요리'] }), NOW));
  assert.ok(k.has('먹방'));
  assert.ok(k.has('고양이'));
  assert.ok(k.has('편의점'));
  assert.ok(k.has('자취요리'));
  assert.ok(!k.has('shorts'));
});

test('rankKeywords: 2개 이상 영상에 나온 단어만, 빠른 영상 쪽이 위', () => {
  const vs = [
    item({ id: '1', title: '#야구 끝내기', views: 9000, hoursAgo: 1 }),
    item({ id: '2', title: '#야구 하이라이트', views: 9000, hoursAgo: 1 }),
    item({ id: '3', title: '#요리 계란', views: 100, hoursAgo: 5 }),
    item({ id: '4', title: '#요리 볶음밥', views: 100, hoursAgo: 5 }),
    item({ id: '5', title: '혼자만 나오는 단어', views: 99999, hoursAgo: 1 }),
  ].map((i) => toVideo(i, NOW));
  const ks = rankKeywords(vs);
  assert.deepEqual(ks.map((k) => k.keyword), ['야구', '요리']);
  assert.deepEqual(ks[0].videoIds, ['1', '2']);
});

test('샘플 데이터로 키워드가 나온다', () => {
  const vs = rankVideos(demoItems(NOW).map((i) => toVideo(i, NOW)).filter(isShort));
  assert.equal(vs.length, 15);
  const top = rankKeywords(vs).map((k) => k.keyword);
  assert.ok(top.includes('편의점'));
  assert.ok(top.includes('챌린지'));
});

test('formatCount / formatAgo', () => {
  assert.equal(formatCount(950), '950');
  assert.equal(formatCount(12_000), '1.2만');
  assert.equal(formatCount(3_100_000), '310만');
  assert.equal(formatCount(150_000_000), '1.5억');
  assert.equal(formatAgo(0.5), '30분 전');
  assert.equal(formatAgo(5.9), '5시간 전');
});

test('youtube: 검색 페이지를 넘기고 할당량을 센다', async () => {
  const calls = [];
  const fake = async (url) => {
    calls.push(new URL(url));
    const page = calls.length;
    return { ok: true, json: async () => ({ items: [{ id: { videoId: `v${page}` } }], nextPageToken: page < 2 ? 't' : undefined }) };
  };
  const r = await searchRecentShortIds({ apiKey: 'k', pages: 3, query: '먹방' }, fake);
  assert.deepEqual(r.ids, ['v1', 'v2']);
  assert.equal(r.quota, 200);
  assert.equal(calls[0].searchParams.get('videoDuration'), 'short');
  assert.equal(calls[0].searchParams.get('relevanceLanguage'), 'ko');
  assert.equal(calls[0].searchParams.get('q'), '먹방');
  assert.equal(calls[1].searchParams.get('pageToken'), 't');
});

test('youtube: 상세 조회는 50개씩 끊는다', async () => {
  const sizes = [];
  const fake = async (url) => {
    sizes.push(new URL(url).searchParams.get('id').split(',').length);
    return { ok: true, json: async () => ({ items: [] }) };
  };
  const ids = Array.from({ length: 120 }, (_, i) => `id${i}`);
  const r = await fetchVideoDetails({ apiKey: 'k', ids }, fake);
  assert.deepEqual(sizes, [50, 50, 20]);
  assert.equal(r.quota, 3);
});

test('youtube: 할당량 초과는 한국어로 안내', async () => {
  const fake = async () => ({ ok: false, status: 403, json: async () => ({ error: { message: 'quota', errors: [{ reason: 'quotaExceeded' }] } }) });
  await assert.rejects(searchRecentShortIds({ apiKey: 'k' }, fake), /할당량/);
});

test('isKorean: 제목이나 채널에 한글이 있어야 한다', () => {
  assert.equal(isKorean({ title: 'Which Baby Is It? #shorts', channel: 'Kids' }), false);
  assert.equal(isKorean({ title: 'BTS cover', channel: '커버하는언니' }), true);
});

test('keywordsOf: ㅋㅋ 같은 자모만 있는 말과 영어 흔한 말은 뺀다', () => {
  const k = keywordsOf(toVideo(item({ title: '고양이 반응 ㅋㅋ ㄷㄷ #funny #comedy #ytshorts' }), NOW));
  assert.deepEqual([...k], ['고양이']);
});
