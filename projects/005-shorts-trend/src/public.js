// 공개 페이지: GitHub Actions가 1시간마다 만드는 data/latest.json을 보여준다.
import { formatAgo, hoursSince } from './trend.js';
import { mountResults } from './view.js';
import { GROUPS } from './snapshot.js';

const $ = (id) => document.getElementById(id);
const view = mountResults({ keywords: $('keywords'), videos: $('videos'), title: $('videosTitle'), clear: $('clearFilter') });

let snapshot = null;

function setStatus(text, isError = false) {
  $('status').hidden = !text;
  $('status').textContent = text;
  $('status').classList.toggle('error', isError);
}

function groupOf(section) {
  return section.group || 'kr'; // 해외 탭이 생기기 전 데이터는 모두 한국
}

function sectionsIn(group) {
  return Object.entries(snapshot.sections).filter(([, s]) => groupOf(s) === group);
}

function currentKey() {
  const key = location.hash.slice(1);
  if (key === 'platforms' || snapshot.sections[key]) return key;
  return Object.keys(snapshot.sections)[0];
}

function tab(href, label, current) {
  const a = document.createElement('a');
  a.href = href;
  a.textContent = label;
  if (current) a.setAttribute('aria-current', 'page');
  return a;
}

function render() {
  const key = currentKey();
  const group = key === 'platforms' ? 'platforms' : groupOf(snapshot.sections[key]);
  $('groups').replaceChildren(
    ...GROUPS.map((g) => {
      if (g.key === 'platforms') return tab('#platforms', g.label, group === g.key);
      const first = sectionsIn(g.key)[0];
      return first ? tab(`#${first[0]}`, g.label, group === g.key) : null;
    }).filter(Boolean),
  );
  const subs = group === 'platforms' ? [] : sectionsIn(group);
  $('tabs').hidden = subs.length < 2;
  $('tabs').replaceChildren(...subs.map(([k, s]) => tab(`#${k}`, s.label, k === key)));

  $('platforms').hidden = group !== 'platforms';
  $('results').hidden = group === 'platforms';
  if (group === 'platforms') return;

  const s = snapshot.sections[key];
  const age = hoursSince(s.updatedAt);
  $('meta').textContent = `${formatAgo(age)} 업데이트 · 최근 ${s.hours}시간 업로드 · 쇼츠 ${s.videos.length}개 분석`;
  view.show(s.videos, s.keywords);
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
