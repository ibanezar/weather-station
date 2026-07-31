#!/usr/bin/env python3
"""
tools/post_to_facebook.py — objavi nov članek na Facebook strani.

Naloži OG sliko članka neposredno prek Graph API POST /{page-id}/photos
(caption = besedilo + link) namesto da bi se zanašal na to, da Facebook sam
pravočasno prebere OG meta podatke s ciljne strani (ta cache je nezanesljiv
v prvih minutah po objavi). Če nalaganje slike iz kakršnegakoli razloga
spodleti, se skript vrne na preprost POST /{page-id}/feed z linkom.

Besedilo objave je prilagojeno tipu članka (razpoznan po predponi sluga):
  vremenski-povzetek-   → mesečni povzetek
  nevihtni-opazovalec-  → nevihtni opazovalec (storm-watch)
  arso-opozorilo-       → ARSO opozorilo (newsjacking)
  invazivk(a|e)-        → invazivke-alarm
  (drugo)               → dnevni/ročni članek

Rabi okoljski spremenljivki FB_PAGE_ID in FB_PAGE_TOKEN (trajni Page Access
Token za stran Meteorec, shranjen kot GitHub secret).

Wired into: .github/workflows/daily-post.yml, monthly-post.yml,
storm-watch.yml, arso-newsjack.yml, invasive-watch.yml
(po uspešnem push-u novega članka na main).

Usage:
  python3 tools/post_to_facebook.py [slug]   # brez sluga: zadnji članek (blog.json[0])
"""
import json, os, sys, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_JSON = os.path.join(ROOT, "blog.json")
SITE = "https://meteorec.si"
GRAPH = "https://graph.facebook.com/v21.0"

PREFIXES = (
    ("vremenski-povzetek-", "📊 Mesečni povzetek"),
    ("nevihtni-opazovalec-", "⛈️ Nevihtni opazovalec"),
    ("arso-opozorilo-", "🚨 ARSO opozorilo"),
    ("invazivka-", "🌿 Invazivke-alarm"),
    ("invazivke-", "🌿 Invazivke-alarm"),
)

# 15. člen ZDMHS: kdor opozorilo pristojnega organa povzame ali objavi, mora
# navesti, da gre za opozorilo pristojnega organa, in čas njegove izdaje. Čas
# izdaje je v povzetku članka (glej generate_arso_newsjack_post.py); tu je še
# izrecna navedba vira, ker je na družbenih omrežjih konteksta strani ni.
ARSO_SOURCE_NOTE = ("Vir opozorila: Agencija RS za okolje (ARSO). To ni opozorilo "
                    "Meteorca — uradna opozorila so na "
                    "https://meteo.arso.gov.si/met/sl/warning/")


def label_for(slug):
    for prefix, label in PREFIXES:
        if slug.startswith(prefix):
            return label
    return None


def build_message(post):
    label = label_for(post["slug"])
    lines = [f"{label}: {post['title']}"] if label else [post["title"]]
    if post.get("summary"):
        lines.append(post["summary"])
    if post["slug"].startswith("arso-opozorilo-"):
        lines.append(ARSO_SOURCE_NOTE)
    post_url = f"{SITE}{post['url']}"
    lines.append(post_url)
    return "\n\n".join(lines), post_url


def post_with_photo(page_id, token, post, message, post_url):
    photo_url = f"{SITE}/og/{post['slug']}.jpg"
    payload = urllib.parse.urlencode({
        "url": photo_url,
        "caption": message,
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{page_id}/photos", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()


def post_link_only(page_id, token, message, post_url):
    payload = urllib.parse.urlencode({
        "message": message,
        "link": post_url,
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{page_id}/feed", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()


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

    message, post_url = build_message(post)

    try:
        body = post_with_photo(page_id, token, post, message, post_url)
        print(f"Facebook: objavljeno (s sliko) — {body}")
        return 0
    except urllib.error.HTTPError as e:
        photo_err = e.read().decode("utf-8", "replace")[:300]
        print(f"Facebook: nalaganje slike spodletelo ({e.code}: {photo_err}), poskušam z navadnim linkom …", file=sys.stderr)

    try:
        body = post_link_only(page_id, token, message, post_url)
        print(f"Facebook: objavljeno (link) — {body}")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Facebook napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
