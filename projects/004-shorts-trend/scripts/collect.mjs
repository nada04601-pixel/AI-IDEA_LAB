#!/usr/bin/env node
// 매시간 GitHub Actions에서 실행: 최근 쇼츠를 수집해 data/latest.json을 갱신한다.
//
//   YOUTUBE_API_KEY=... node scripts/collect.mjs <이전 latest.json> <저장할 latest.json>
//
// 오류가 나도 지난 데이터는 그대로 두고 errors에 기록한다 (페이지가 비지 않도록).
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { searchRecentShortIds, fetchVideoDetails } from '../src/youtube.js';
import { sectionsForRun, buildSection, mergeSnapshot } from '../src/snapshot.js';

const [prevPath, outPath] = process.argv.slice(2);
if (!prevPath || !outPath) {
  console.error('사용법: node scripts/collect.mjs <이전 latest.json> <저장할 latest.json>');
  process.exit(2);
}

const apiKey = process.env.YOUTUBE_API_KEY;
const regionCode = process.env.REGION || 'KR';
const hours = Number(process.env.HOURS || 24);
const allPages = Number(process.env.ALL_PAGES || 2);

let prev = null;
try {
  prev = JSON.parse(await readFile(prevPath, 'utf8'));
} catch {
  console.log('이전 데이터 없음 — 새로 만듭니다.');
}

if (!apiKey) {
  console.log('::warning::YOUTUBE_API_KEY 시크릿이 없어 수집을 건너뜁니다.');
  process.exit(0);
}

const now = new Date();
const updated = {};
const errors = [];
let quota = 0;

for (const section of sectionsForRun(now)) {
  try {
    const pages = section.key === 'all' ? allPages : 1;
    const found = await searchRecentShortIds({ apiKey, regionCode, hours, pages, query: section.query });
    const details = await fetchVideoDetails({ apiKey, ids: found.ids });
    quota += found.quota + details.quota;
    updated[section.key] = buildSection(section, details.items, {
      prev: prev?.sections?.[section.key],
      now: now.getTime(),
      hours,
      koreanOnly: regionCode === 'KR',
    });
    const s = updated[section.key];
    console.log(`${section.label}: 쇼츠 ${s.videos.length}개, 키워드 ${s.keywords.length}개`);
  } catch (err) {
    errors.push({ section: section.key, message: err.message, at: now.toISOString() });
    console.log(`::warning::${section.label} 수집 실패: ${err.message}`);
    if (err.reason === 'quotaExceeded' || err.reason === 'keyInvalid') break;
  }
}

const snapshot = mergeSnapshot(prev, updated, { now: now.getTime(), regionCode, errors });
await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, JSON.stringify(snapshot));
console.log(`저장: ${outPath} (할당량 약 ${quota}단위 사용)`);
