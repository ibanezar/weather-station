#!/usr/bin/env python3
"""
tools/check_links.py — mrtve povezave (link-check.yml, tedensko).

1. NOTRANJE: vsak href/src="/…" v vseh HTML datotekah repozitorija mora kazati na
   datoteko, ki jo GitHub Pages postreže (pot, pot.html ali pot/index.html).
   Brez omrežja, preveri vseh ~5000 strani v nekaj sekundah. crnivec-site/ se
   razreši znotraj sebe (to je koren domene crnivec.si).
2. ZUNANJE (--external): vsak različen zunanji URL enkrat (HEAD, ob 405 GET),
   vzporedno, s časovno omejitvijo. 4xx/5xx in nedosegljivost sta napaka;
   403/429 sta samo opomba (strežniki pogosto zavrnejo robote).

Izhod `broken` za GITHUB_OUTPUT; workflow odpre/zapre issue `broken-links`.

Usage:
    python3 tools/check_links.py [--external] [--report links.md]
"""
import concurrent.futures as cf
import glob
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK_RE = re.compile(r'''(?:href|src)\s*=\s*["']([^"'#?\s][^"'\s]*)["']''', re.I)
SKIP_DIRS = ("node_modules", ".git", "makro-inbox")
# Strani, ki niso objavljene ali so namenoma predloge.
SKIP_FILES = ("crnivec-brand/",)
# Brskalniški UA: nekateri strežniki (npr. Weather Underground) robotom vrnejo 404.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
SOFT = {403, 429, 999}


def html_files():
    for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
        rel = os.path.relpath(p, ROOT)
        if rel.split(os.sep)[0] in SKIP_DIRS or rel.startswith(SKIP_FILES):
            continue
        yield rel


def site_root(rel):
    return "crnivec-site" if rel.startswith("crnivec-site" + os.sep) else ""


def exists(root, path):
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0]).lstrip("/")
    base = os.path.join(ROOT, root, path)
    if path == "" or path.endswith("/"):
        return os.path.exists(os.path.join(base, "index.html"))
    return (os.path.isfile(base) or os.path.isfile(base + ".html")
            or os.path.isfile(os.path.join(base, "index.html")))


def scan():
    internal = defaultdict(set)   # manjkajoča pot -> strani
    external = defaultdict(set)   # zunanji URL -> strani
    for rel in html_files():
        try:
            h = open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # Predloge in kode v <script> (npr. '/vreme/'+y+'/') niso povezave.
        h = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", h)
        root = site_root(rel)
        for url in LINK_RE.findall(h):
            if url.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:", "{", "$")):
                continue
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith(("http://", "https://")):
                host = urllib.parse.urlparse(url).netloc
                if host in ("meteorec.si", "www.meteorec.si"):
                    if not exists("", urllib.parse.urlparse(url).path):
                        internal[urllib.parse.urlparse(url).path].add(rel)
                elif host == "crnivec.si":
                    if not exists("crnivec-site", urllib.parse.urlparse(url).path):
                        internal["crnivec.si" + urllib.parse.urlparse(url).path].add(rel)
                else:
                    external[url.split("#")[0]].add(rel)
            elif url.startswith("/"):
                if not exists(root, url):
                    internal[(root + ":" if root else "") + url.split("#")[0].split("?")[0]].add(rel)
            # relativne povezave (redke) se razrešijo glede na mapo strani
            elif not re.match(r"^[a-z]+:", url):
                target = os.path.normpath(os.path.join(os.path.dirname(rel), url.split("#")[0].split("?")[0]))
                if not target.startswith("..") and not exists("", "/" + target.replace(os.sep, "/")):
                    internal[target].add(rel)
    return internal, external


def check_external(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD":   # veliko strežnikov HEAD obravnava narobe — poskusi GET
                continue
            return e.code
        except Exception:  # noqa: BLE001
            if method == "HEAD":
                continue
            return None
    return None


def main():
    args = sys.argv[1:]
    internal, external = scan()
    lines = ["# Mrtve povezave", ""]
    broken = len(internal)
    lines.append(f"## Notranje ({len(internal)})")
    for path, pages in sorted(internal.items(), key=lambda x: -len(x[1])):
        ex = ", ".join(sorted(pages)[:3]) + (f" … (+{len(pages) - 3})" if len(pages) > 3 else "")
        lines.append(f"- `{path}` — {len(pages)} strani: {ex}")
    if "--external" in args:
        urls = sorted(external)
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            res = dict(zip(urls, ex.map(check_external, urls)))
        bad = {u: s for u, s in res.items() if s is None or (s >= 400 and s not in SOFT)}
        soft = {u: s for u, s in res.items() if s in SOFT}
        broken += len(bad)
        lines += ["", f"## Zunanje ({len(bad)} od {len(urls)})"]
        for u, s in sorted(bad.items()):
            pages = sorted(external[u])
            lines.append(f"- {u} — {s or 'nedosegljivo'} — {pages[0]}" + (f" (+{len(pages) - 1})" if len(pages) > 1 else ""))
        if soft:
            lines += ["", f"Zavrnili robota (403/429, ni nujno mrtvo): {len(soft)}"]
    if broken == 0:
        lines.append("\n✅ Ni mrtvih povezav.")
    md = "\n".join(lines) + "\n"
    print(md)
    if "--report" in args:
        with open(args[args.index("--report") + 1], "w", encoding="utf-8") as f:
            f.write(md)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"broken={broken}\n")


if __name__ == "__main__":
    main()
