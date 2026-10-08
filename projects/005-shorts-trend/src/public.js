// 공개 페이지: GitHub Actions가 1시간마다 만드는 data/latest.json을 보여준다.
import { formatAgo, hoursSince } from './trend.js';
import { mountResults } from './view.js';

const $ = (id) => document.getElementById(id);
const view = mountResults({ keywords: $('keywords'), videos: $('videos'), title: $('videosTitle'), clear: $('clearFilter') });

let snapshot = null;

function setStatus(text, isError = false) {
  $('status').hidden = !text;
  $('status').textContent = text;
  $('status').classList.toggle('error', isError);
}

function currentKey() {
  const key = location.hash.slice(1);
  return snapshot.sections[key] ? key : Object.keys(snapshot.sections)[0];
}

function render() {
  const key = currentKey();
  $('tabs').replaceChildren(
    ...Object.entries(snapshot.sections).map(([k, s]) => {
      const a = document.createElement('a');
      a.href = `#${k}`;
      a.textContent = s.label;
      if (k === key) a.setAttribute('aria-current', 'page');
      return a;
    }),
  );
  const s = snapshot.sections[key];
  const age = hoursSince(s.updatedAt);
  $('meta').textContent = `${formatAgo(age)} 업데이트 · 최근 ${s.hours}시간 업로드 · 쇼츠 ${s.videos.length}개 분석`;
  view.show(s.videos, s.keywords);
  $('results').hidden = false;
}

async function load() {
  try {
    const res = await fetch(`data/latest.json?t=${Math.floor(Date.now() / 300_000)}`);
    if (!res.ok) throw new Error(res.status);
    snapshot = await res.json();
  } catch {
    setStatus('아직 수집된 데이터가 없어요. 첫 수집이 끝나면 여기에 순위가 나옵니다.');
    return;
  }
  if (!Object.keys(snapshot.sections || {}).length) {
    setStatus('아직 수집된 데이터가 없어요. 첫 수집이 끝나면 여기에 순위가 나옵니다.');
    return;
  }
  render();
}

window.addEventListener('hashchange', () => snapshot && render());
load();
