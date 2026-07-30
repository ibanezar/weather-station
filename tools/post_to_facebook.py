#!/usr/bin/env python3
"""
tools/post_to_facebook.py — objavi povezavo do novega članka na Facebook strani.

Kliče Graph API POST /{page-id}/feed z "message" (naslov + povzetek) in "link"
(URL članka) — Facebook sam potegne OG sliko/naslov s ciljne strani, zato ni
treba ročno nalagati slike.

Rabi okoljski spremenljivki FB_PAGE_ID in FB_PAGE_TOKEN (trajni Page Access
Token za stran Meteorec, shranjen kot GitHub secret).

Wired into: .github/workflows/daily-post.yml, .github/workflows/monthly-post.yml
(po uspešnem push-u novega članka na main).

Usage:
  python3 tools/post_to_facebook.py [slug]   # brez sluga: zadnji članek (blog.json[0])
"""
import json, os, sys, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_JSON = os.path.join(ROOT, "blog.json")

GRAPH_URL = "https://graph.facebook.com/v21.0/{page_id}/feed"


def main():
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        print("FB_PAGE_ID / FB_PAGE_TOKEN nista nastavljena — preskačem objavo na Facebook.", file=sys.stderr)
        return 0

    posts = json.load(open(BLOG_JSON, encoding="utf-8"))
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    post = next((p for p in posts if p.get("slug") == slug), None) if slug else posts[0]
    if not post:
        print(f"Ni najdenega članka za objavo na Facebook (slug={slug!r}).", file=sys.stderr)
        return 1

    post_url = f"https://meteorec.si{post['url']}"
    message = post["title"]
    if post.get("summary"):
        message += "\n\n" + post["summary"]

    payload = urllib.parse.urlencode({
        "message": message,
        "link": post_url,
        "access_token": token,
    }).encode()

    req = urllib.request.Request(
        GRAPH_URL.format(page_id=page_id),
        data=payload,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"Facebook: objavljeno — {r.read().decode()}")
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Facebook napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
