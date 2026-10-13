// 수집 스크립트 테스트용: YouTube API 대신 샘플 데이터를 돌려준다.
import { demoItems } from '../../src/demo.js';

const items = demoItems();
globalThis.fetch = async (url) => {
  const u = new URL(url);
  calls.push(u.pathname);
  if (process.env.FAKE_FAIL === 'quota') {
    return { ok: false, status: 403, json: async () => ({ error: { message: 'quota', errors: [{ reason: 'quotaExceeded' }] } }) };
  }
  if (u.hostname === 'graph.threads.net') {
    if (process.env.FAKE_FAIL === 'threads-token') {
      return { ok: false, status: 400, json: async () => ({ error: { message: 'expired', code: 190 } }) };
    }
    const data = items.map((it) => ({
      id: `${it.id}`,
      text: it.snippet.title,
      media_type: 'VIDEO',
      permalink: `https://www.threads.net/@u/post/${it.id}`,
      timestamp: it.snippet.publishedAt,
      username: 'u',
    }));
    return { ok: true, json: async () => ({ data }) };
  }
  if (u.pathname.endsWith('/search')) {
    return { ok: true, json: async () => ({ items: items.map((it) => ({ id: { videoId: it.id } })) }) };
  }
  const ids = new Set(u.searchParams.get('id').split(','));
  return { ok: true, json: async () => ({ items: items.filter((it) => ids.has(it.id)) }) };
};
const calls = [];
process.on('exit', () => console.log(`FAKE_CALLS=${calls.length}`));
