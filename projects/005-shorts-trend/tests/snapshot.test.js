import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SECTIONS, YOUTUBE_SECTIONS, THREADS_SECTION, sectionsForRun, buildSection, buildThreadsSection, mergeSnapshot } from '../src/snapshot.js';
import { searchThreadsVideos } from '../src/threads.js';
import { demoItems } from '../src/demo.js';

const NOW = Date.parse('2026-10-08T12:00:00Z');
const ALL = SECTIONS[0];

test('매시간 한국 전체 + 하나, 분야·해외는 돌아가며 모두 갱신된다', () => {
  const seen = new Set();
  for (let h = 0; h < YOUTUBE_SECTIONS.length - 1; h++) {
    const run = sectionsForRun(new Date(NOW + h * 3_600_000));
    assert.equal(run.length, 2);
    assert.equal(run[0].key, 'all');
    seen.add(run[1].key);
  }
  assert.equal(seen.size, YOUTUBE_SECTIONS.length - 1);
  assert.ok(!seen.has('threads'));
});

test('buildSection: 순위·키워드, 설명 같은 큰 필드는 저장하지 않는다', () => {
  const s = buildSection(ALL, demoItems(NOW), { now: NOW, hours: 24 });
  assert.equal(s.videos.length, 15);
  assert.equal(s.updatedAt, new Date(NOW).toISOString());
  assert.ok(s.videos[0].viewsPerHour >= s.videos[1].viewsPerHour);
  assert.ok(!('description' in s.videos[0]));
  assert.ok(!('recentPerHour' in s.videos[0]));
  assert.ok(s.keywords.some((k) => k.keyword === '편의점'));
});

test('buildSection: 지난 수집에도 있던 영상은 그 사이 시간당 증가량을 붙인다', () => {
  const prev = buildSection(ALL, demoItems(NOW - 3_600_000), { now: NOW - 3_600_000, hours: 24 });
  prev.videos[0].views -= 5000; // 1시간 전에는 5000회 적었다고 가정
  const id = prev.videos[0].id;
  const s = buildSection(ALL, demoItems(NOW), { prev, now: NOW, hours: 24 });
  assert.equal(s.videos.find((v) => v.id === id).recentPerHour, 5000);
});

test('buildSection: 지난 수집이 너무 오래됐으면 증가량을 계산하지 않는다', () => {
  const prev = buildSection(ALL, demoItems(NOW), { now: NOW - 24 * 3_600_000, hours: 24 });
  const s = buildSection(ALL, demoItems(NOW), { prev, now: NOW, hours: 24 });
  assert.ok(s.videos.every((v) => v.recentPerHour == null));
});

test('mergeSnapshot: 이번에 안 돈 섹션은 지난 결과를 유지, 순서는 SECTIONS 기준', () => {
  const food = { label: '먹방·요리', videos: [], keywords: [] };
  const prev = { version: 1, sections: { food } };
  const all = { label: '전체', videos: [], keywords: [] };
  const snap = mergeSnapshot(prev, { all }, { now: NOW, regionCode: 'KR' });
  assert.deepEqual(Object.keys(snap.sections), ['all', 'food']);
  assert.equal(snap.sections.food, food);
  assert.equal(mergeSnapshot({ version: 0, sections: { food } }, {}, {}).sections.food, undefined);
});

function runCollector(env, prev) {
  const dir = mkdtempSync(join(tmpdir(), 'shorts-'));
  const prevPath = join(dir, 'prev.json');
  const outPath = join(dir, 'out', 'latest.json');
  if (prev) writeFileSync(prevPath, JSON.stringify(prev));
  const stdout = execFileSync(
    process.execPath,
    ['--import', './tests/fixtures/fake-fetch.mjs', 'scripts/collect.mjs', prevPath, outPath],
    { env: { ...process.env, ...env }, encoding: 'utf8' },
  );
  let out = null;
  try { out = JSON.parse(readFileSync(outPath, 'utf8')); } catch { /* 저장 안 됨 */ }
  return { stdout, out };
}

test('collect.mjs: 키가 없으면 아무것도 쓰지 않고 정상 종료', () => {
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: '', THREADS_ACCESS_TOKEN: '' });
  assert.match(stdout, /건너뜁니다/);
  assert.equal(out, null);
});

test('collect.mjs: 전체 + 분야 하나를 수집해 저장', () => {
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: 'k', THREADS_ACCESS_TOKEN: '' });
  assert.equal(out.version, 1);
  assert.equal(Object.keys(out.sections).length, 2);
  assert.equal(out.sections.all.videos.length, 15);
  assert.deepEqual(out.errors, []);
  assert.match(stdout, /할당량 약 \d+단위/);
});

test('collect.mjs: 할당량 초과면 지난 데이터를 유지하고 오류를 기록', () => {
  const prev = { version: 1, sections: { all: { label: '전체', updatedAt: '2026-10-08T00:00:00Z', videos: [], keywords: [] } } };
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: 'k', THREADS_ACCESS_TOKEN: '', FAKE_FAIL: 'quota' }, prev);
  assert.deepEqual(out.sections, prev.sections);
  assert.equal(out.errors[0].section, 'all');
  assert.match(stdout, /FAKE_CALLS=1\b/); // 첫 실패 후 바로 멈춘다
});

test('buildSection: 한국 섹션은 한글 영상만 남긴다', () => {
  const items = demoItems(NOW);
  items[0].snippet.title = 'Which Baby Is It? #shorts';
  items[0].snippet.channelTitle = 'Kids';
  assert.equal(buildSection({ ...ALL, only: undefined }, items, { now: NOW, hours: 24 }).videos.length, 15);
  assert.equal(buildSection(ALL, items, { now: NOW, hours: 24 }).videos.length, 14);
});

test('해외 섹션: 일본은 가나가 있는 영상만, 미국은 거르지 않는다', () => {
  const jp = SECTIONS.find((s) => s.key === 'jp');
  const us = SECTIONS.find((s) => s.key === 'us');
  const items = demoItems(NOW);
  items[0].snippet.title = '猫が初めて雪を見た #shorts';
  items[0].snippet.channelTitle = 'ねこ日記';
  const s = buildSection(jp, items, { now: NOW, hours: 24 });
  assert.deepEqual(s.videos.map((v) => v.id), ['demo0']);
  assert.equal(s.group, 'world');
  assert.equal(s.regionCode, 'JP');
  assert.equal(buildSection(us, items, { now: NOW, hours: 24 }).videos.length, 15);
});

test('해외 섹션도 돌아가며 갱신되고, 전세계는 국가 제한 없이 검색한다', () => {
  const rotating = YOUTUBE_SECTIONS.filter((s) => s.key !== 'all');
  const keys = new Set();
  for (let h = 0; h < rotating.length; h++) keys.add(sectionsForRun(new Date(NOW + h * 3_600_000))[1].key);
  for (const key of ['us', 'jp', 'global']) assert.ok(keys.has(key));
  assert.equal(SECTIONS.find((s) => s.key === 'global').regionCode, '');
});

function threadsPosts() {
  return demoItems(NOW).map((it, i) => ({
    id: String(i),
    text: it.snippet.title,
    media_type: 'VIDEO',
    permalink: `https://www.threads.net/@u/post/${i}`,
    timestamp: it.snippet.publishedAt,
    username: 'u',
  }));
}

test('threads: 검색어마다 인기순·영상만 검색하고, 여러 검색어 상위 게시물을 앞에 둔다', async () => {
  const calls = [];
  const fake = async (url) => {
    const u = new URL(url);
    calls.push(u);
    const posts = threadsPosts();
    // 두 번째 검색어에서는 게시물 순서를 뒤집는다 → 양쪽에서 높은 '1'이 1등
    const data = u.searchParams.get('q') === 'a' ? [posts[0], posts[1], posts[2]] : [posts[1], posts[2], posts[0]];
    return { ok: true, json: async () => ({ data }) };
  };
  const r = await searchThreadsVideos({ accessToken: 't', queries: ['a', 'b'], now: NOW }, fake);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].searchParams.get('search_type'), 'TOP');
  assert.equal(calls[0].searchParams.get('media_type'), 'VIDEO');
  assert.equal(calls[0].searchParams.get('since'), String((NOW - 24 * 3_600_000) / 1000));
  assert.deepEqual(r.map((p) => p.id), ['1', '0', '2']);
});

test('threads: 토큰 만료는 알아보기 쉬운 오류로 바꾼다', async () => {
  const fake = async () => ({ ok: false, status: 400, json: async () => ({ error: { code: 190, message: 'x' } }) });
  await assert.rejects(searchThreadsVideos({ accessToken: 't', queries: ['a'] }, fake), (err) => {
    assert.equal(err.reason, 'keyInvalid');
    assert.match(err.message, /THREADS_ACCESS_TOKEN/);
    return true;
  });
});

test('buildThreadsSection: 한글 게시물만, 기간 밖은 빼고, 키워드에는 조회수가 없다', () => {
  const posts = threadsPosts().map((p) => ({ ...p, query: 'a', score: 1 }));
  posts[0].text = 'Cute dog';
  posts[1].timestamp = new Date(NOW - 30 * 3_600_000).toISOString();
  const s = buildThreadsSection(THREADS_SECTION, posts, { now: NOW, hours: 24 });
  assert.equal(s.videos.length, 13);
  assert.equal(s.source, 'threads');
  assert.equal(s.group, 'platforms');
  assert.equal(s.videos[0].url, posts[2].permalink);
  assert.equal(s.videos[0].views, undefined);
  assert.ok(s.keywords.some((k) => k.keyword === '챌린지'));
  assert.ok(s.keywords.every((k) => !('viewsPerHour' in k)));
});

test('collect.mjs: 스레드 토큰만 있어도 스레드를 수집하고, 실패하면 오류만 기록한다', () => {
  const ok = runCollector({ YOUTUBE_API_KEY: '', THREADS_ACCESS_TOKEN: 't' });
  assert.deepEqual(Object.keys(ok.out.sections), ['threads']);
  assert.equal(ok.out.sections.threads.videos.length, 15);
  assert.match(ok.stdout, /FAKE_CALLS=6\b/); // 검색어 6개

  const prev = { version: 1, sections: { threads: ok.out.sections.threads } };
  const bad = runCollector({ YOUTUBE_API_KEY: '', THREADS_ACCESS_TOKEN: 't', FAKE_FAIL: 'threads-token' }, prev);
  assert.deepEqual(bad.out.sections, prev.sections);
  assert.equal(bad.out.errors[0].section, 'threads');
});
