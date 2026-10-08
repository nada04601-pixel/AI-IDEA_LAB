import { toVideo, isShort, rankVideos, rankKeywords, formatCount, formatAgo } from './trend.js';
import { searchRecentShortIds, fetchVideoDetails } from './youtube.js';
import { demoItems } from './demo.js';

const $ = (id) => document.getElementById(id);
const KEY_STORAGE = 'shorts-trend:apiKey';

const state = { videos: [], keywords: [], filter: null };

function load(key) {
  try { return localStorage.getItem(key) || ''; } catch { return ''; }
}
function save(key, value) {
  try { localStorage.setItem(key, value); } catch { /* 저장 불가 환경 */ }
}

$('apiKey').value = load(KEY_STORAGE);

function setStatus(text, isError = false) {
  const el = $('status');
  el.hidden = !text;
  el.textContent = text;
  el.classList.toggle('error', isError);
}

function analyze(items, metaText) {
  const now = Date.now();
  const videos = rankVideos(items.map((it) => toVideo(it, now)).filter(isShort));
  state.videos = videos;
  state.keywords = rankKeywords(videos, { minCount: videos.length >= 40 ? 3 : 2 });
  state.filter = null;
  $('meta').textContent = `${metaText} · 쇼츠 ${videos.length}개 분석 · ${new Date(now).toLocaleString('ko-KR')}`;
  render();
  $('results').hidden = false;
}

function render() {
  const kwList = $('keywords');
  kwList.replaceChildren(
    ...state.keywords.map((k, i) => {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = state.filter === k.keyword ? 'kw active' : 'kw';
      btn.innerHTML = `<span class="rank">${i + 1}</span><span class="word"></span><span class="num">${k.count}개 · 시간당 ${formatCount(k.viewsPerHour)}</span>`;
      btn.querySelector('.word').textContent = k.keyword;
      btn.addEventListener('click', () => {
        state.filter = state.filter === k.keyword ? null : k.keyword;
        render();
      });
      li.append(btn);
      return li;
    }),
  );
  if (!state.keywords.length) kwList.innerHTML = '<li class="empty">겹치는 키워드가 아직 없어요. 검색 범위를 늘려 보세요.</li>';

  const kw = state.keywords.find((k) => k.keyword === state.filter);
  const shown = kw ? state.videos.filter((v) => kw.videoIds.includes(v.id)) : state.videos;
  $('videosTitle').textContent = kw ? `🚀 "${kw.keyword}" 떡상 쇼츠` : '🚀 떡상 쇼츠 순위';
  $('clearFilter').hidden = !kw;

  $('videos').replaceChildren(...shown.map((v, i) => videoItem(v, i + 1)));
  if (!shown.length) $('videos').innerHTML = '<li class="empty">조건에 맞는 쇼츠가 없어요.</li>';
}

function videoItem(v, rank) {
  const li = document.createElement('li');
  const demo = v.id.startsWith('demo');
  const a = document.createElement(demo ? 'div' : 'a');
  a.className = 'video';
  if (!demo) {
    a.href = `https://www.youtube.com/shorts/${v.id}`;
    a.target = '_blank';
    a.rel = 'noopener';
  }
  a.innerHTML = `
    <span class="rank">${rank}</span>
    <span class="thumb">${v.thumbnail ? '<img alt="" loading="lazy" />' : '▶'}</span>
    <span class="info">
      <span class="title"></span>
      <span class="channel"></span>
      <span class="stats">
        <b>시간당 ${formatCount(v.viewsPerHour)}회</b>
        · 조회 ${formatCount(v.views)} · 좋아요 ${formatCount(v.likes)}
        · ${formatAgo(v.hours)} · ${v.seconds}초
      </span>
    </span>`;
  if (v.thumbnail) a.querySelector('img').src = v.thumbnail;
  a.querySelector('.title').textContent = v.title;
  a.querySelector('.channel').textContent = v.channel + (demo ? ' (샘플)' : '');
  li.append(a);
  return li;
}

$('clearFilter').addEventListener('click', () => {
  state.filter = null;
  render();
});

$('demo').addEventListener('click', () => {
  setStatus('');
  analyze(demoItems(), '⚠️ 샘플 데이터 (실제 영상 아님)');
});

$('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const apiKey = $('apiKey').value.trim();
  if (!apiKey) {
    setStatus('API 키를 넣어 주세요. 키 없이 화면만 보려면 "샘플 데이터로 보기"를 누르세요.', true);
    return;
  }
  save(KEY_STORAGE, apiKey);
  const opts = {
    apiKey,
    regionCode: $('region').value,
    hours: Number($('hours').value),
    pages: Number($('pages').value),
    query: $('query').value.trim(),
  };
  $('run').disabled = true;
  try {
    setStatus('최근 쇼츠를 찾는 중…');
    const found = await searchRecentShortIds(opts);
    setStatus(`${found.ids.length}개 영상의 조회수를 가져오는 중…`);
    const details = await fetchVideoDetails({ apiKey, ids: found.ids });
    setStatus('');
    const region = $('region').selectedOptions[0].textContent;
    const scope = opts.query ? `"${opts.query}"` : '전체';
    analyze(details.items, `${region} · 최근 ${opts.hours}시간 · ${scope} · 할당량 ${found.quota + details.quota}단위 사용`);
  } catch (err) {
    setStatus(err.message || String(err), true);
  } finally {
    $('run').disabled = false;
  }
});
