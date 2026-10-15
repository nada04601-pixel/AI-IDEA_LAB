"""영상 내려받기·검색 (기획서 Module 1). yt-dlp를 먼저 쓰고, 실패하면 Playwright(실제 브라우저)로 시도한다.

샤오홍슈·도우인은 로그인하지 않으면 막히는 경우가 많아 부계정 쿠키(secrets/cookies.txt, Netscape 형식)를 쓴다.
사이트 구조가 바뀌면 가장 먼저 깨지는 부분이므로, 실패하면 '무엇이 막혔고 → 무엇을 하면 되는지'를 알려준다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0.0.0 Safari/537.36")
PAGE_TIMEOUT_MS = 45_000
PLATFORMS = {
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com", "rednote.com"),  # rednote.com = 샤오홍슈 국제판 (로그인 따로)
    "douyin": ("douyin.com", "iesdouyin.com"),
    "tiktok": ("tiktok.com",),
}
SEARCH = {  # 플랫폼: (검색 주소, 결과 링크에서 영상 글을 찾는 정규식)
    "xiaohongshu": ("https://{host}/search_result?keyword={q}&source=web_search_result_notes",
                    re.compile(r"/(?:explore|search_result|discovery/item)/([0-9a-f]{24})")),
    "douyin": ("https://www.douyin.com/search/{q}?type=video", re.compile(r"/video/(\d{15,22})")),
}


class DownloadError(Exception):
    """사용자에게 그대로 보여줄 수 있는 내려받기 오류."""


@dataclass
class Fetched:
    file: Path
    title: str = ""
    description: str = ""
    author: str = ""
    location: str = ""
    extra: dict = field(default_factory=dict)


class Downloader(Protocol):
    name: str

    def fetch(self, url: str, out_dir: Path, stem: str) -> Fetched:
        """url의 영상을 out_dir/stem.mp4로 내려받는다. 실패하면 DownloadError."""


class Searcher(Protocol):
    def search(self, platform: str, keyword: str, limit: int) -> list[str]:
        """platform에서 keyword로 찾은 영상 글 주소들."""


def platform_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for name, domains in PLATFORMS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return "other"


def xhs_host(cookies: Path | None) -> str:
    """샤오홍슈 검색에 쓸 사이트. 쿠키가 국제판(rednote.com) 것뿐이면 그쪽으로 (두 사이트는 로그인이 따로다)."""
    domains = {c["domain"].lstrip(".") for c in load_netscape_cookies(cookies)} if cookies and cookies.is_file() else set()
    if any(d.endswith("rednote.com") for d in domains) and not any(d.endswith("xiaohongshu.com") for d in domains):
        return "www.rednote.com"
    return "www.xiaohongshu.com"


def load_netscape_cookies(path: Path) -> list[dict]:
    """cookies.txt(Netscape 형식) → Playwright 쿠키 목록."""
    cookies = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        http_only = line.startswith("#HttpOnly_")
        if http_only:
            line = line[len("#HttpOnly_"):]
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, path_, secure, expires, name, value = parts[:7]
        cookie = {"name": name, "value": value, "domain": domain, "path": path_ or "/",
                  "secure": secure.upper() == "TRUE", "httpOnly": http_only}
        if expires.isdigit() and int(expires) > 0:
            cookie["expires"] = int(expires)
        cookies.append(cookie)
    return cookies


def _downloaded(out_dir: Path, stem: str) -> Path | None:
    files = [p for p in out_dir.glob(f"{stem}.*") if p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv")]
    return max(files, key=lambda p: p.stat().st_size) if files else None


class _SilentLogger:
    """yt-dlp가 화면에 직접 쓰는 오류를 숨긴다 (같은 내용을 DownloadError로 한국어 안내와 함께 보여준다)."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class YtDlpDownloader:
    name = "yt-dlp"

    def __init__(self, cookies: Path | None, ffmpeg: str | None):
        self.cookies, self.ffmpeg = cookies, ffmpeg

    def fetch(self, url: str, out_dir: Path, stem: str) -> Fetched:
        import yt_dlp

        opts = {"outtmpl": str(out_dir / f"{stem}.%(ext)s"), "format": "bv*+ba/b", "merge_output_format": "mp4",
                "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True, "retries": 3,
                "socket_timeout": 30, "logger": _SilentLogger()}
        if self.cookies:
            opts["cookiefile"] = str(self.cookies)
        if self.ffmpeg:
            opts["ffmpeg_location"] = str(Path(self.ffmpeg).parent)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True) or {}
        except Exception as e:  # noqa: BLE001 — yt-dlp는 사이트마다 다양한 예외를 낸다
            raise DownloadError(f"yt-dlp: {str(e).strip()[:200]}") from e
        file = _downloaded(out_dir, stem)
        if not file:
            raise DownloadError("yt-dlp: 영상 파일이 만들어지지 않았습니다 (이미지 글이거나 영상이 없는 글일 수 있음).")
        return Fetched(file=file, title=info.get("title") or "", description=info.get("description") or "",
                       author=info.get("uploader") or info.get("channel") or "",
                       location=info.get("location") or info.get("ip_location") or "")


class PlaywrightDownloader:
    """실제 크롬으로 글을 열고, 페이지가 불러오는 영상 주소를 잡아 내려받는다."""

    name = "playwright"

    def __init__(self, cookies: Path | None):
        self.cookies = cookies

    def fetch(self, url: str, out_dir: Path, stem: str) -> Fetched:
        try:
            from playwright.sync_api import Error as PWError, sync_playwright
        except ImportError as e:
            raise DownloadError("playwright가 설치되지 않았습니다 → setup.bat을 다시 실행하세요.") from e
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    ctx = browser.new_context(user_agent=USER_AGENT, locale="zh-CN")
                    if self.cookies:
                        ctx.add_cookies(load_netscape_cookies(self.cookies))
                    page = ctx.new_page()
                    seen: dict[str, int] = {}

                    def on_response(resp):
                        ctype = resp.headers.get("content-type", "")
                        if ctype.startswith("video/") or re.search(r"\.mp4(\?|$)", resp.url):
                            seen[resp.url] = int(resp.headers.get("content-length") or 0)

                    page.on("response", on_response)
                    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    page.wait_for_timeout(6000)
                    for src in page.eval_on_selector_all("video", "els => els.map(e => e.currentSrc || e.src)"):
                        if src and src.startswith("http"):
                            seen.setdefault(src, 0)
                    title = page.title()
                    desc = page.eval_on_selector_all('meta[name="description"], meta[property="og:description"]',
                                                     "els => els.map(e => e.content).join(' ')")
                    if not seen:
                        raise DownloadError("playwright: 페이지에서 영상 주소를 찾지 못했습니다 "
                                            "(로그인 필요·이미지 글·스트리밍(blob) 영상일 수 있음).")
                    video_url = max(seen, key=lambda u: seen[u])
                    resp = ctx.request.get(video_url, headers={"Referer": url, "User-Agent": USER_AGENT},
                                           timeout=120_000)
                    if not resp.ok:
                        raise DownloadError(f"playwright: 영상 주소 응답 {resp.status}")
                    file = out_dir / f"{stem}.mp4"
                    file.write_bytes(resp.body())
                finally:
                    browser.close()
        except PWError as e:
            hint = " → `python -m playwright install chromium`" if "Executable doesn't exist" in str(e) else ""
            raise DownloadError(f"playwright: {str(e).splitlines()[0][:200]}{hint}") from e
        return Fetched(file=file, title=title, description=desc)


class PlaywrightSearcher:
    """플랫폼 검색 결과 페이지를 열어 영상 글 링크를 모은다. 로그인(쿠키)이 없으면 대부분 막힌다."""

    def __init__(self, cookies: Path | None, scrolls: int = 4):
        self.cookies, self.scrolls = cookies, scrolls
        self.hosts = {"xiaohongshu": xhs_host(cookies)}

    def search(self, platform: str, keyword: str, limit: int) -> list[str]:
        if platform not in SEARCH:
            return []
        page_url, pattern = SEARCH[platform]
        try:
            from playwright.sync_api import Error as PWError, sync_playwright
        except ImportError as e:
            raise DownloadError("playwright가 설치되지 않았습니다 → setup.bat을 다시 실행하세요.") from e
        found: dict[str, str] = {}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    ctx = browser.new_context(user_agent=USER_AGENT, locale="zh-CN")
                    if self.cookies:
                        ctx.add_cookies(load_netscape_cookies(self.cookies))
                    page = ctx.new_page()
                    page.goto(page_url.format(q=quote(keyword), host=self.hosts.get(platform, "")),
                              wait_until="domcontentloaded",
                              timeout=PAGE_TIMEOUT_MS)
                    page.wait_for_timeout(4000)
                    for _ in range(self.scrolls):
                        collect_links(page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"),
                                      pattern, found)
                        if len(found) >= limit:
                            break
                        page.mouse.wheel(0, 2500)
                        page.wait_for_timeout(2000)
                finally:
                    browser.close()
        except PWError as e:
            raise DownloadError(f"검색 실패: {str(e).splitlines()[0][:200]}") from e
        return list(found.values())[:limit]


def collect_links(hrefs: list[str], pattern: re.Pattern, found: dict[str, str]) -> None:
    """검색 결과 링크를 글 ID별로 모은다. 같은 글이면 접근 토큰(xsec_token)이 붙은 링크를 고른다
    (샤오홍슈·rednote는 토큰 없이 열면 보안 오류 300031로 404)."""
    for href in hrefs:
        m = pattern.search(href or "")
        if m and (m.group(1) not in found or ("xsec_token=" in href and "xsec_token=" not in found[m.group(1)])):
            found[m.group(1)] = href


def fetch_any(downloaders: list[Downloader], url: str, out_dir: Path, stem: str) -> tuple[Fetched, list[str]]:
    """순서대로 시도한다. (결과, 앞에서 실패한 이유들). 모두 실패하면 DownloadError."""
    errors = []
    for d in downloaders:
        try:
            return d.fetch(url, out_dir, stem), errors
        except DownloadError as e:
            errors.append(str(e))
    raise DownloadError(" / ".join(errors) or "내려받을 방법이 없습니다.")
