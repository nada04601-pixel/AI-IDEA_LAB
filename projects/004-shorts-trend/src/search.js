// 직접 검색 페이지: 사용자 본인의 API 키로 바로 분석한다.
import { toVideo, isShort, isKorean, rankVideos, rankKeywords, KOREAN_BROAD_QUERY } from './trend.js';
import { searchRecentShortIds, fetchVideoDetails } from './youtube.js';
import { demoItems } from './demo.js';
import { mountResults } from './view.js';

const $ = (id) => document.getElementById(id);
const KEY_STORAGE = 'shorts-trend:apiKey';

const view = mountResults({ keywords: $('keywords'), videos: $('videos'), title: $('videosTitle'), clear: $('clearFilter') });

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

function analyze(items, metaText, { koreanOnly = false } = {}) {
  const now = Date.now();
  const shorts = items.map((it) => toVideo(it, now)).filter(isShort);
  const videos = rankVideos(koreanOnly ? shorts.filter(isKorean) : shorts);
  const keywords = rankKeywords(videos, { minCount: videos.length >= 40 ? 3 : 2 });
  $('meta').textContent = `${metaText} · 쇼츠 ${videos.length}개 분석 · ${new Date(now).toLocaleString('ko-KR')}`;
  view.show(videos, keywords);
  $('results').hidden = false;
}

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
    // 한국은 검색어 없이 찾으면 해외 영상이 대부분이라 흔한 한국어 단어로 찾고 한글 영상만 남긴다
    const korea = opts.regionCode === 'KR';
    const found = await searchRecentShortIds({ ...opts, query: opts.query || (korea ? KOREAN_BROAD_QUERY : '') });
    setStatus(`${found.ids.length}개 영상의 조회수를 가져오는 중…`);
    const details = await fetchVideoDetails({ apiKey, ids: found.ids });
    setStatus('');
    const region = $('region').selectedOptions[0].textContent;
    const scope = opts.query ? `"${opts.query}"` : '전체';
    analyze(details.items, `${region} · 최근 ${opts.hours}시간 · ${scope} · 할당량 ${found.quota + details.quota}단위 사용`, { koreanOnly: korea });
  } catch (err) {
    setStatus(err.message || String(err), true);
  } finally {
    $('run').disabled = false;
  }
});
