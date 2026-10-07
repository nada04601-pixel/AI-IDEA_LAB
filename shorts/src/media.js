// URL 복사·썸네일(이미지) 저장 (브라우저 전용, 공개 페이지와 직접 검색 페이지 공용)
// 영상 파일 다운로드는 YouTube 서비스 약관(다운로드 링크를 YouTube가 직접 주는 경우만 허용)에 어긋나 제공하지 않는다.

// 유튜브 주소 → 영상 ID. shorts/watch/youtu.be/embed/live 형식과 ID만 넣은 경우를 받는다.
export function youtubeIdFrom(input) {
  const text = String(input || '').trim();
  if (/^[\w-]{11}$/.test(text)) return text;
  let u;
  try {
    u = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
  } catch {
    return null;
  }
  const host = u.hostname.replace(/^(www|m|music)\./, '');
  let id = null;
  if (host === 'youtu.be') id = u.pathname.split('/')[1];
  else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
    id = u.searchParams.get('v') || u.pathname.match(/^\/(?:shorts|embed|live|v)\/([^/?#]+)/)?.[1];
  }
  return id && /^[\w-]{11}$/.test(id) ? id : null;
}

export function isImageUrl(input) {
  try {
    const u = new URL(String(input).trim());
    return u.protocol === 'https:' && /\.(jpe?g|png|webp|gif)$/i.test(u.pathname);
  } catch {
    return false;
  }
}

// 큰 것부터. maxresdefault는 없는 영상이 있다 (그러면 120px 회색 이미지가 온다).
export function youtubeThumbnails(id) {
  return [`https://i.ytimg.com/vi/${id}/maxresdefault.jpg`, `https://i.ytimg.com/vi/${id}/hqdefault.jpg`];
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // http 주소나 오래된 브라우저: 숨긴 입력칸으로 복사
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

// 유튜브 썸네일 중 실제로 있는 가장 큰 것
export async function bestYoutubeThumbnail(id) {
  const [maxres, hq] = youtubeThumbnails(id);
  const img = await loadImage(maxres);
  return img && img.naturalWidth > 120 ? maxres : hq;
}

// 이미지를 파일로 저장한다. 다른 사이트 이미지라 브라우저가 막으면(CORS) 새 탭으로 열어 직접 저장하게 한다.
// 반환: 'saved' | 'opened'
export async function downloadImage(url, filename) {
  try {
    const res = await fetch(url, { mode: 'cors' });
    if (!res.ok) throw new Error(res.status);
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    return 'saved';
  } catch {
    window.open(url, '_blank', 'noopener');
    return 'opened';
  }
}

// 버튼 글자를 잠깐 바꿔 결과를 알린다
export function flash(button, text, ms = 1500) {
  const original = button.dataset.label || button.textContent;
  button.dataset.label = original;
  button.textContent = text;
  clearTimeout(button._flash);
  button._flash = setTimeout(() => (button.textContent = original), ms);
}

// "URL로 이미지 저장" 칸: 유튜브 영상 주소 → 썸네일, 이미지 주소 → 그 이미지
// els: { form, input, result } — 각각 DOM 요소
export function mountSaver(els) {
  els.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = els.input.value.trim();
    const id = youtubeIdFrom(text);
    let src;
    let name;
    if (id) {
      src = await bestYoutubeThumbnail(id);
      name = `${id}.jpg`;
    } else if (isImageUrl(text)) {
      src = text;
      name = new URL(text).pathname.split('/').pop();
    } else {
      els.result.innerHTML = '<p class="status error">유튜브 영상 주소(쇼츠·일반·youtu.be)나 https 이미지 주소(.jpg .png .webp .gif)를 넣어 주세요.</p>';
      return;
    }
    els.result.innerHTML = `
      <img alt="미리보기" />
      <div class="actions">
        <button type="button" class="save">🖼️ 이미지 저장</button>
        <button type="button" class="ghost copy">🔗 이미지 주소 복사</button>
      </div>`;
    els.result.querySelector('img').src = src;
    const save = els.result.querySelector('.save');
    save.addEventListener('click', async () => {
      const r = await downloadImage(src, name);
      flash(save, r === 'saved' ? '✅ 저장됨' : '새 탭에서 길게 눌러 저장', 2500);
    });
    const copy = els.result.querySelector('.copy');
    copy.addEventListener('click', async () => flash(copy, (await copyText(src)) ? '✅ 복사됨' : '복사 실패'));
  });
}
