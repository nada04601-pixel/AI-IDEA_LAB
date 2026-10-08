import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SECTIONS, sectionsForRun, buildSection, mergeSnapshot } from '../src/snapshot.js';
import { demoItems } from '../src/demo.js';

const NOW = Date.parse('2026-10-08T12:00:00Z');
const ALL = SECTIONS[0];

test('매시간 전체 + 분야 하나, 분야는 돌아가며 모두 갱신된다', () => {
  const seen = new Set();
  for (let h = 0; h < SECTIONS.length - 1; h++) {
    const run = sectionsForRun(new Date(NOW + h * 3_600_000));
    assert.equal(run.length, 2);
    assert.equal(run[0].key, 'all');
    seen.add(run[1].key);
  }
  assert.equal(seen.size, SECTIONS.length - 1);
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
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: '' });
  assert.match(stdout, /건너뜁니다/);
  assert.equal(out, null);
});

test('collect.mjs: 전체 + 분야 하나를 수집해 저장', () => {
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: 'k' });
  assert.equal(out.version, 1);
  assert.equal(Object.keys(out.sections).length, 2);
  assert.equal(out.sections.all.videos.length, 15);
  assert.deepEqual(out.errors, []);
  assert.match(stdout, /할당량 약 \d+단위/);
});

test('collect.mjs: 할당량 초과면 지난 데이터를 유지하고 오류를 기록', () => {
  const prev = { version: 1, sections: { all: { label: '전체', updatedAt: '2026-10-08T00:00:00Z', videos: [], keywords: [] } } };
  const { stdout, out } = runCollector({ YOUTUBE_API_KEY: 'k', FAKE_FAIL: 'quota' }, prev);
  assert.deepEqual(out.sections, prev.sections);
  assert.equal(out.errors[0].section, 'all');
  assert.match(stdout, /FAKE_CALLS=1\b/); // 첫 실패 후 바로 멈춘다
});
