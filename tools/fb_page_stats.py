#!/usr/bin/env python3
"""
tools/fb_page_stats.py — prikaže odziv (deljenja) zadnjih objav na Facebook
strani Meteorec.

Ročno orodje (ni vklopljeno v noben workflow) — poženeš ga, ko te zanima,
kako so se odzvale zadnje objave. Rabi FB_PAGE_ID in FB_PAGE_TOKEN (isti
GitHub secreta kot tools/post_to_facebook.py) — lokalno ju nastaviš kot
okoljski spremenljivki pred zagonom.

Opomba: števila všečkov/komentarjev (likes.summary, comments.summary,
reactions.summary) prek Graph API v tem primeru NISO dostopna brez polnega
Meta App Review (Advanced Access za pages_read_engagement/pages_read_user_
content) -- to presega dovoljenja, odobrena z Business Verification. Ta
skript zato izpiše samo tisto, kar je dostopno s trenutnimi dovoljenji:
osnovne podatke o objavi in število deljenj.

Usage:
  FB_PAGE_ID=... FB_PAGE_TOKEN=... python3 tools/fb_page_stats.py [--limit N]
"""
import json, os, sys, urllib.request, urllib.parse

GRAPH = "https://graph.facebook.com/v21.0"
FIELDS = "message,created_time,permalink_url,shares"


def main():
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN")
    if not page_id or not token:
        sys.exit("FB_PAGE_ID / FB_PAGE_TOKEN morata biti nastavljena.")

    limit = 10
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])

    qs = urllib.parse.urlencode({"fields": FIELDS, "limit": limit, "access_token": token})
    req = urllib.request.Request(f"{GRAPH}/{page_id}/posts?{qs}")
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)

    for p in data.get("data", []):
        msg = (p.get("message") or "").split("\n")[0][:70]
        shares = p.get("shares", {}).get("count", 0)
        print(f"{p['created_time']}  🔁{shares:>3}  {msg}")
        print(f"   {p.get('permalink_url', '')}")


if __name__ == "__main__":
    main()
