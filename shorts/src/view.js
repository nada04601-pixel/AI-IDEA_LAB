// 키워드 순위 + 쇼츠 순위 화면 (공개 페이지와 직접 검색 페이지 공용)
import { formatCount, formatAgo, hoursSince } from './trend.js';
import { copyText, downloadImage, bestYoutubeThumbnail, flash } from './media.js';

// els: { keywords, videos, title, clear } — 각각 DOM 요소
export function mountResults(els) {
  const state = { videos: [], keywords: [], filter: null, noun: '쇼츠' };

  function render() {
    els.keywords.replaceChildren(...state.keywords.map(keywordItem));
    if (!state.keywords.length) {
      els.keywords.innerHTML = '<li class="empty">겹치는 키워드가 아직 없어요.</li>';
    }

    const kw = state.keywords.find((k) => k.keyword === state.filter);
    const shown = kw ? state.videos.filter((v) => kw.videoIds.includes(v.id)) : state.videos;
    els.title.textContent = kw ? `🚀 "${kw.keyword}" 떡상 ${state.noun}` : `🚀 떡상 ${state.noun} 순위`;
    els.clear.hidden = !kw;

    els.videos.replaceChildren(...shown.map((v, i) => videoItem(v, i + 1)));
    if (!shown.length) els.videos.innerHTML = '<li class="empty">조건에 맞는 쇼츠가 없어요.</li>';
  }

  function keywordItem(k, i) {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = state.filter === k.keyword ? 'kw active' : 'kw';
    const speed = k.viewsPerHour != null ? ` · 시간당 ${formatCount(k.viewsPerHour)}` : ''; // 스레드는 조회수가 없다
    btn.innerHTML = `<span class="rank">${i + 1}</span><span class="word"></span><span class="num">${k.count}개${speed}</span>`;
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
    // noun: 순위 제목에 쓸 이름 (쇼츠·스레드)
    show(videos, keywords, { noun = '쇼츠' } = {}) {
      Object.assign(state, { videos, keywords, filter: null, noun });
      render();
    },
  };
}

function videoItem(v, rank) {
  const li = document.createElement('li');
  // 외부 데이터의 링크는 https만 쓴다 (javascript: 같은 주소 차단)
  const demo = v.id.startsWith('demo') || (v.url != null && !/^https:\/\//.test(v.url));
  const a = document.createElement(demo ? 'div' : 'a');
  a.className = 'video';
  if (!demo) {
    a.href = v.url || `https://www.youtube.com/shorts/${v.id}`;
    a.target = '_blank';
    a.rel = 'noopener';
  }
  const recent = v.recentPerHour != null ? ` · <span class="recent">지금 시간당 +${formatCount(v.recentPerHour)}</span>` : '';
  // 스레드 게시물: 조회수·길이가 없어 업로드 시각과 찾은 검색어만 보여준다
  const stats = v.views == null
    ? `${formatAgo(hoursSince(v.publishedAt))} · '<span class="q"></span>' 인기 검색`
    : `<b>평균 시간당 ${formatCount(v.viewsPerHour)}회</b>${recent}
        · 조회 ${formatCount(v.views)} · 좋아요 ${formatCount(v.likes)}
        · ${formatAgo(hoursSince(v.publishedAt))} · ${v.seconds}초`;
  a.innerHTML = `
    <span class="rank">${rank}</span>
    <span class="thumb">${v.thumbnail ? '<img alt="" loading="lazy" />' : '▶'}</span>
    <span class="info">
      <span class="title"></span>
      <span class="channel"></span>
      <span class="stats">${stats}</span>
    </span>`;
  if (v.thumbnail) a.querySelector('img').src = v.thumbnail;
  a.querySelector('.title').textContent = v.title;
  a.querySelector('.channel').textContent = v.channel + (demo ? ' (샘플)' : '');
  if (v.views == null) a.querySelector('.q').textContent = v.query || '';
  li.className = 'video-card';
  li.append(a);
  if (!demo) li.append(cardActions(v, a.href));
  return li;
}

// 카드 아래 버튼: 주소 복사, 썸네일 저장
function cardActions(v, url) {
  const box = document.createElement('div');
  box.className = 'card-actions';
  const copy = smallButton('🔗 URL 복사', async () => flash(copy, (await copyText(url)) ? '✅ 복사됨' : '복사 실패'));
  box.append(copy);
  const youtube = !v.url;
  if (youtube || /^https:\/\//.test(v.thumbnail || '')) {
    const save = smallButton('🖼️ 썸네일 저장', async () => {
      const src = youtube ? await bestYoutubeThumbnail(v.id) : v.thumbnail;
      const result = await downloadImage(src, `${youtube ? v.id : v.id.replace(/^th_/, 'threads_')}.jpg`);
      flash(save, result === 'saved' ? '✅ 저장됨' : '새 탭에서 길게 눌러 저장', 2500);
    });
    box.append(save);
  }
  return box;
}

function smallButton(label, onClick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'ghost small';
  b.textContent = label;
  b.addEventListener('click', onClick);
  return b;
}
