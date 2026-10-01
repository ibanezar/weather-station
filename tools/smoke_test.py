#!/usr/bin/env python3
"""
tools/smoke_test.py — dimni test JAVNE strani po objavi (smoke-test.yml).

Zelena objava na GitHub Pages ne pove, ali stran res deluje: generator lahko
zapiše prazno stran, pokvarjen JSON-LD, napačen canonical ali OG sliko, ki je
ni. Ta skript gre po ključnih straneh (CORE iz seo_audit.py — isti seznam kot
sitemap, ne drugi) in crnivec.si ter preveri, kar vidi obiskovalec/iskalnik:

  - HTTP 200 (brez preusmeritve na drugo stran),
  - <title> obstaja, canonical kaže nase,
  - vsak JSON-LD blok se razčleni,
  - stran ni očitno prazna (vsaj MIN_TEXT znakov besedila),
  - og:image res obstaja (200, slika),
  - ključni viri naslovne strani (style.min.css, app.min.js, history.json).

Napake gredo v poročilo (--report) in izhod `fail` za GITHUB_OUTPUT; workflow
odpre/zapre issue z oznako `smoke-fail` (isti vzorec kot stale-output).

Usage:
    python3 tools/smoke_test.py [--report smoke.md] [--base https://meteorec.si]
"""
import concurrent.futures as cf
import html as html_lib
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_audit import CORE  # noqa: E402

UA = "Mozilla/5.0 (compatible; meteorec-smoke/1.0; +https://meteorec.si/o-postaji.html)"
MIN_TEXT = 400
CRNIVEC = ["https://crnivec.si/", "https://crnivec.si/lipa/", "https://crnivec.si/igra/"]
ASSETS = ["/style.min.css", "/app.min.js", "/history.json", "/sitemap.xml", "/llms.txt"]
LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
OGIMG_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')


def fetch(url, method="GET", timeout=25):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read() if method == "GET" else b""
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as e:
        return e.code, url, "", b""
    except Exception as e:  # noqa: BLE001 — omrežje, TLS, časovna omejitev
        return None, url, str(e)[:120], b""


def visible_text(h):
    h = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<head[\s\S]*?</head>", " ", h)
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def check_page(url):
    """Seznam napak za eno HTML stran; og:image vrne posebej (preveri se enkrat)."""
    errs = []
    st, final, ctype, body = fetch(url)
    if st != 200:
        return [f"HTTP {st if st else 'napaka ' + ctype}"], None
    if final.rstrip("/") != url.rstrip("/"):
        errs.append(f"preusmeritev na {final}")
    h = body.decode("utf-8", "replace")
    t = TITLE_RE.search(h)
    if not t or not t.group(1).strip():
        errs.append("brez <title>")
    c = CANON_RE.search(h)
    if not c:
        errs.append("brez canonical")
    elif c.group(1).rstrip("/") != url.rstrip("/"):
        errs.append(f"canonical kaže drugam: {c.group(1)}")
    for i, block in enumerate(LDJSON_RE.findall(h), 1):
        try:
            json.loads(block)
        except ValueError as e:
            errs.append(f"JSON-LD #{i} se ne razčleni ({str(e)[:60]})")
    if len(visible_text(h)) < MIN_TEXT:
        errs.append(f"skoraj prazna stran ({len(visible_text(h))} znakov besedila)")
    og = OGIMG_RE.search(h)
    return errs, (og.group(1) if og else None)


def check_image(url):
    st, _f, ctype, _b = fetch(url, method="HEAD")
    if st == 405:  # nekateri strežniki HEAD ne podpirajo
        st, _f, ctype, _b = fetch(url)
    if st != 200:
        return f"HTTP {st}"
    if not ctype.startswith("image/"):
        return f"ni slika ({ctype})"
    return None


def run(base):
    pages = [f"{base}/{p}" for p in CORE] + CRNIVEC
    problems = {}
    og_urls = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for url, (errs, og) in zip(pages, ex.map(check_page, pages)):
            if errs:
                problems[url] = errs
            if og:
                og_urls.setdefault(og, url)
        for og, res in zip(og_urls, ex.map(check_image, list(og_urls))):
            if res:
                problems.setdefault(og_urls[og], []).append(f"og:image {og}: {res}")
        assets = [f"{base}{a}" for a in ASSETS]
        for url, (st, _f, ctype, body) in zip(assets, ex.map(fetch, assets)):
            if st != 200 or not body:
                problems[url] = [f"HTTP {st}" if st != 200 else "prazna datoteka"]
            elif url.endswith(".json"):
                try:
                    json.loads(body)
                except ValueError:
                    problems[url] = ["ni veljaven JSON"]
    return pages, problems


def report(pages, problems):
    lines = ["# Dimni test javne strani", "",
             f"Preverjenih strani: {len(pages)} + {len(ASSETS)} virov. Napak: **{len(problems)}**.", ""]
    for url, errs in sorted(problems.items()):
        lines.append(f"- {url}")
        lines += [f"  - {e}" for e in errs]
    if not problems:
        lines.append("✅ Vse strani in viri so v redu.")
    return "\n".join(lines) + "\n"


def main():
    args = sys.argv[1:]
    base = args[args.index("--base") + 1].rstrip("/") if "--base" in args else "https://meteorec.si"
    pages, problems = run(base)
    md = report(pages, problems)
    print(md)
    if "--report" in args:
        with open(args[args.index("--report") + 1], "w", encoding="utf-8") as f:
            f.write(md)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"fail={len(problems)}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    main()
