#!/usr/bin/env python3
"""정적 사이트 빌더 (표준 라이브러리만 사용).

src/pages/**/*.html  -> 레이아웃(src/layout.html)을 입혀 site/ 로 출력
src/assets/**        -> site/assets/ 로 그대로 복사
sitemap.xml, robots.txt, ads.txt, CNAME 자동 생성

사용법:  python3 build.py
"""
import datetime
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "site"

NAV = [
    ("/", "홈"),
    ("/tools/", "계산기"),
    ("/guides/", "생활 정보"),
    ("/about.html", "회사 소개"),
    ("/contact.html", "문의하기"),
]

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def load_config():
    cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
    cfg["domain"] = cfg["domain"].rstrip("/")
    return cfg


def parse_page(path):
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = FRONT_MATTER.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        text = text[m.end():]
    return meta, text


def url_for(rel_path):
    url = "/" + rel_path.as_posix()
    if url.endswith("/index.html"):
        url = url[: -len("index.html")]
    return url


def render_nav(url):
    items = []
    for href, label in NAV:
        active = url == href or (href != "/" and url.startswith(href))
        current = ' aria-current="page"' if active else ""
        items.append(f'<li><a href="{href}"{current}>{label}</a></li>')
    return "\n          ".join(items)


def head_extra(cfg):
    parts = []
    if cfg.get("search_console_verification"):
        parts.append(f'<meta name="google-site-verification" content="{html.escape(cfg["search_console_verification"])}">')
    if cfg.get("naver_site_verification"):
        parts.append(f'<meta name="naver-site-verification" content="{html.escape(cfg["naver_site_verification"])}">')
    if cfg.get("adsense_client"):
        client = html.escape(cfg["adsense_client"])
        parts.append(f'<meta name="google-adsense-account" content="{client}">')
        parts.append(
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={client}" '
            'crossorigin="anonymous"></script>'
        )
    if cfg.get("ga_measurement_id"):
        gid = html.escape(cfg["ga_measurement_id"])
        parts.append(f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>')
        parts.append(
            "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
            f"gtag('js',new Date());gtag('config','{gid}');</script>"
        )
    return "\n  ".join(parts)


def build():
    cfg = load_config()
    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    year = str(datetime.date.today().year)

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")

    sitemap_urls = []
    pages_dir = SRC / "pages"
    for path in sorted(pages_dir.rglob("*.html")):
        rel = path.relative_to(pages_dir)
        meta, body = parse_page(path)
        url = url_for(rel)
        title = meta.get("title", cfg["site_name"])
        full_title = title if url == "/" else f"{title} | {cfg['site_name']}"
        scripts = "".join(
            f'\n  <script src="{s.strip()}" defer></script>'
            for s in meta.get("scripts", "").split(",") if s.strip()
        )
        values = {
            "title": html.escape(full_title),
            "description": html.escape(meta.get("description", cfg["site_tagline"])),
            "canonical": cfg["domain"] + url,
            "nav": render_nav(url),
            "head_extra": head_extra(cfg),
            "scripts": scripts,
            "content": body,
            "year": year,
            **{k: html.escape(str(v)) for k, v in cfg.items() if k not in ("domain",)},
            "domain": cfg["domain"],
        }
        page = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), layout)
        # 본문 안의 {{site_name}}, {{email}} 같은 설정값도 치환
        page = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), page)

        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")

        if meta.get("sitemap", "yes") != "no":
            sitemap_urls.append((cfg["domain"] + url, meta.get("updated", datetime.date.today().isoformat())))

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in sitemap_urls:
        sitemap.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    sitemap.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")

    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {cfg['domain']}/sitemap.xml\n", encoding="utf-8"
    )

    if cfg.get("adsense_client"):
        pub = cfg["adsense_client"].replace("ca-", "")
        (OUT / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")

    host = re.sub(r"^https?://", "", cfg["domain"])
    if "example.com" not in host:
        (OUT / "CNAME").write_text(host + "\n", encoding="utf-8")

    print(f"built {len(sitemap_urls)} pages -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
