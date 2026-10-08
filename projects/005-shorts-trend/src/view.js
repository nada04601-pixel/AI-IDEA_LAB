// 키워드 순위 + 쇼츠 순위 화면 (공개 페이지와 직접 검색 페이지 공용)
import { formatCount, formatAgo, hoursSince } from './trend.js';

// els: { keywords, videos, title, clear } — 각각 DOM 요소
export function mountResults(els) {
  const state = { videos: [], keywords: [], filter: null };

  function render() {
    els.keywords.replaceChildren(...state.keywords.map(keywordItem));
    if (!state.keywords.length) {
      els.keywords.innerHTML = '<li class="empty">겹치는 키워드가 아직 없어요.</li>';
    }

    const kw = state.keywords.find((k) => k.keyword === state.filter);
    const shown = kw ? state.videos.filter((v) => kw.videoIds.includes(v.id)) : state.videos;
    els.title.textContent = kw ? `🚀 "${kw.keyword}" 떡상 쇼츠` : '🚀 떡상 쇼츠 순위';
    els.clear.hidden = !kw;

    els.videos.replaceChildren(...shown.map((v, i) => videoItem(v, i + 1)));
    if (!shown.length) els.videos.innerHTML = '<li class="empty">조건에 맞는 쇼츠가 없어요.</li>';
  }

  function keywordItem(k, i) {
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
  }

  els.clear.addEventListener('click', () => {
    state.filter = null;
    render();
  });

  return {
    show(videos, keywords) {
      Object.assign(state, { videos, keywords, filter: null });
      render();
    },
  };
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
  const recent = v.recentPerHour != null ? ` · <span class="recent">지금 시간당 +${formatCount(v.recentPerHour)}</span>` : '';
  a.innerHTML = `
    <span class="rank">${rank}</span>
    <span class="thumb">${v.thumbnail ? '<img alt="" loading="lazy" />' : '▶'}</span>
    <span class="info">
      <span class="title"></span>
      <span class="channel"></span>
      <span class="stats">
        <b>평균 시간당 ${formatCount(v.viewsPerHour)}회</b>${recent}
        · 조회 ${formatCount(v.views)} · 좋아요 ${formatCount(v.likes)}
        · ${formatAgo(hoursSince(v.publishedAt))} · ${v.seconds}초
      </span>
    </span>`;
  if (v.thumbnail) a.querySelector('img').src = v.thumbnail;
  a.querySelector('.title').textContent = v.title;
  a.querySelector('.channel').textContent = v.channel + (demo ? ' (샘플)' : '');
  li.append(a);
  return li;
}
