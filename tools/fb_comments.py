#!/usr/bin/env python3
"""
tools/fb_comments.py — ročno orodje za pregled in odgovarjanje na komentarje
na Facebook strani Meteorec.

Ni vklopljeno v noben workflow -- namenoma ostaja ročno, ker gre za javno
komuniciranje v imenu strani. Rabi FB_PAGE_ID in FB_PAGE_TOKEN (isti GitHub
secreta kot ostala fb_*/post_to_facebook orodja), lokalno nastavljena kot
okoljski spremenljivki.

Usage:
  python3 tools/fb_comments.py list [--posts N] [--unanswered-only]
  python3 tools/fb_comments.py reply <comment_id> "besedilo odgovora"
"""
import os, sys, json, urllib.request, urllib.parse, urllib.error

GRAPH = "https://graph.facebook.com/v21.0"


def api_get(path, **params):
    token = os.environ["FB_PAGE_TOKEN"]
    qs = urllib.parse.urlencode({**params, "access_token": token})
    req = urllib.request.Request(f"{GRAPH}/{path}?{qs}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def api_post(path, **params):
    token = os.environ["FB_PAGE_TOKEN"]
    payload = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def list_comments(n_posts=10, unanswered_only=False):
    page_id = os.environ["FB_PAGE_ID"]
    fields = "message,permalink_url,comments.limit(50){message,from,created_time,id,comments.limit(5){from}}"
    data = api_get(f"{page_id}/posts", fields=fields, limit=n_posts)

    found = 0
    for post in data.get("data", []):
        comments = post.get("comments", {}).get("data", [])
        if not comments:
            continue
        for c in comments:
            has_page_reply = any(
                r.get("from", {}).get("id") == page_id
                for r in c.get("comments", {}).get("data", [])
            )
            if unanswered_only and has_page_reply:
                continue
            found += 1
            title = (post.get("message") or "").split("\n")[0][:60]
            author = c.get("from", {}).get("name", "?")
            flag = "  [odgovorjeno]" if has_page_reply else ""
            print(f"[{c['id']}]{flag} {author} — {c.get('created_time', '')}")
            print(f"  na članku: {title}")
            print(f"  \"{c.get('message', '')}\"")
            print(f"  {post.get('permalink_url', '')}")
            print()
    if found == 0:
        print("Ni komentarjev" + (" brez odgovora." if unanswered_only else "."))


def reply(comment_id, message):
    result = api_post(f"{comment_id}/comments", message=message)
    print(f"Odgovorjeno: {result}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    try:
        if cmd == "list":
            n_posts = 10
            unanswered_only = "--unanswered-only" in sys.argv
            if "--posts" in sys.argv:
                i = sys.argv.index("--posts")
                n_posts = int(sys.argv[i + 1])
            list_comments(n_posts, unanswered_only)
        elif cmd == "reply":
            if len(sys.argv) < 4:
                sys.exit("Uporaba: python3 tools/fb_comments.py reply <comment_id> \"besedilo\"")
            reply(sys.argv[2], sys.argv[3])
        else:
            sys.exit(__doc__)
    except urllib.error.HTTPError as e:
        sys.exit(f"Napaka {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")


if __name__ == "__main__":
    main()
