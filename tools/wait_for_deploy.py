#!/usr/bin/env python3
"""
tools/wait_for_deploy.py — počaka, da GitHub Pages dejansko postreže na novo
objavljen članek (stran + OG slika), preden se sproži objava na FB/IG.

Brez tega FB/IG koraki (ki tečejo takoj po `git push`) občasno ujamejo 404,
ker deploy GitHub Pages traja nekaj deset sekund do minuto -- FB si napačno
(404) stanje trajno zapomni v predogled linka, IG pa ne uspe prenesti slike.

Vedno konča z izhodno kodo 0 (best-effort) -- tudi če po timeoutu stran še
ni live, naj FB/IG koraka vseeno poskusita (continue-on-error itak ne podre
workflowa).

Usage:
  python3 tools/wait_for_deploy.py [slug ...]   # brez sluga: zadnji članek (blog.json[0])
"""
import json, os, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_JSON = os.path.join(ROOT, "blog.json")
SITE = "https://meteorec.si"
MAX_WAIT_SECONDS = 120
POLL_INTERVAL = 5


def url_is_live(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 200
    except Exception:
        return False


def wait_for(post):
    page_url = f"{SITE}{post['url']}"
    og_url = f"{SITE}/og/{post['slug']}.jpg"
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        if url_is_live(page_url) and url_is_live(og_url):
            print(f"Live: {page_url}")
            return True
        time.sleep(POLL_INTERVAL)
    print(f"Po {MAX_WAIT_SECONDS}s stran še ni live — nadaljujem vseeno: {page_url}", file=sys.stderr)
    return False


def main():
    posts = json.load(open(BLOG_JSON, encoding="utf-8"))
    slugs = sys.argv[1:] or [None]
    for slug in slugs:
        post = next((p for p in posts if p.get("slug") == slug), None) if slug else posts[0]
        if not post:
            print(f"Ni najdenega članka (slug={slug!r}) — preskačem čakanje.", file=sys.stderr)
            continue
        wait_for(post)
    return 0


if __name__ == "__main__":
    sys.exit(main())
