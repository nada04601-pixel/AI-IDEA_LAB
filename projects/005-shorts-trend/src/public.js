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

// 틱톡·인스타 링크 안내는 수집 데이터가 없는 고정 탭이다
const LINKS = ['platforms', { label: '🔗 틱톡·인스타', group: 'platforms' }];

function tabsIn(group) {
  return group === 'platforms' ? [...sectionsIn(group), LINKS] : sectionsIn(group);
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
      const first = tabsIn(g.key)[0];
      return first ? tab(`#${first[0]}`, g.label, group === g.key) : null;
    }).filter(Boolean),
  );
  const subs = tabsIn(group);
  $('tabs').hidden = subs.length < 2;
  $('tabs').replaceChildren(...subs.map(([k, s]) => tab(`#${k}`, s.label, k === key)));

  $('platforms').hidden = key !== 'platforms';
  $('results').hidden = key === 'platforms';
  if (key === 'platforms') return;

  const s = snapshot.sections[key];
  const threads = s.source === 'threads';
  const age = hoursSince(s.updatedAt);
  $('meta').textContent = threads
    ? `${formatAgo(age)} 업데이트 · 최근 ${s.hours}시간 · 스레드 인기 영상 게시물 ${s.videos.length}개`
    : `${formatAgo(age)} 업데이트 · 최근 ${s.hours}시간 업로드 · 쇼츠 ${s.videos.length}개 분석`;
  $('videosHint').innerHTML = threads
    ? '스레드가 인기순으로 보여주는 영상 게시물입니다. 스레드 API는 다른 사람 게시물의 조회수를 주지 않아, 여러 검색어에서 높은 순위로 나온 게시물을 앞에 놓았어요.'
    : '<b>평균 시간당</b>은 올라온 뒤 지금까지의 평균 속도, <b>지금 시간당</b>은 지난 수집 이후 늘어난 속도입니다.';
  view.show(s.videos, s.keywords, { noun: threads ? '스레드' : '쇼츠' });
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
