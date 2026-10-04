#!/usr/bin/env python3
"""
tools/post_to_facebook.py — objavi nov članek na Facebook strani.

Privzeto (FB_POST_MODE=link) objavi POST /{page-id}/feed z linkom: Facebook
sam izriše predogled iz OG meta podatkov (delovni tokovi pred objavo počakajo,
da GitHub Pages stran postreže). Podatki strani Meteorec (2. 7.–1. 10. 2026,
Meta Business Suite) so pokazali, da so objave z linkom imele 5–15 % klikov na
doseženo osebo (20 klikov pri dosegu 137), objave s sliko in linkom v prvem
komentarju pa <1 % — doseg je bil pri obeh podoben. Prejšnje vedenje (OG slika
prek /photos, link v prvem komentarju) ostane na voljo z FB_POST_MODE=photo;
če link objava spodleti, skript pade nazaj na /photos.

Link ima oznake UTM (utm_source=facebook, utm_medium=social, utm_campaign=<tip
članka>), da jih GA4 loči od drugih virov.

Pred objavo skript pogleda zadnje objave na strani in preskoči članek, ki je
že objavljen (isti link ali isto besedilo v zadnjih 3 dneh) — opaženo je bilo,
da je isti članek šel dvakrat. Preverjanje je best-effort: če API zahteve ne
dovoli, se objavi kot prej. FB_FORCE=1 ga izklopi (social-repost.yml).

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


# Kratka imena tipov za utm_campaign (po predponi sluga).
CAMPAIGNS = (
    ("vremenski-povzetek-", "mesecni-povzetek"),
    ("nevihtni-opazovalec-", "nevihtni-opazovalec"),
    ("arso-opozorilo-", "arso-opozorilo"),
    ("invazivka-", "invazivke"),
    ("invazivke-", "invazivke"),
)
DEDUP_DAYS = 3


def campaign_for(slug):
    for prefix, name in CAMPAIGNS:
        if slug.startswith(prefix):
            return name
    return "clanek"


def with_utm(url, slug):
    q = urllib.parse.urlencode({"utm_source": "facebook", "utm_medium": "social",
                                "utm_campaign": campaign_for(slug)})
    return url + ("&" if "?" in url else "?") + q


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
    return "\n\n".join(lines), post_url


def post_with_photo(page_id, token, post, message):
    """Objavi sliko brez linka v besedilu. Vrne post_id (za komentar z linkom)."""
    photo_url = f"{SITE}/og/{post['slug']}.jpg"
    payload = urllib.parse.urlencode({
        "url": photo_url,
        "caption": message,
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{page_id}/photos", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    return data.get("post_id") or data.get("id")


def post_link_only(page_id, token, message, post_url):
    payload = urllib.parse.urlencode({
        "message": message,
        "link": post_url,
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{page_id}/feed", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()


def post_link_comment(post_id, token, post_url):
    """Doda link kot prvi komentar — namesto v besedilu objave, ker linki v
    caption/body naj bi zaviral doseg (glej PR/CLAUDE.md kontekst distribucije)."""
    payload = urllib.parse.urlencode({
        "message": f"Cel članek: {post_url}",
        "access_token": token,
    }).encode()
    req = urllib.request.Request(f"{GRAPH}/{post_id}/comments", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()


def already_posted(page_id, token, post_url, message):
    """Best-effort: ali je na strani v zadnjih DEDUP_DAYS dneh že isti članek?

    Vrne True samo, če je zadetek zanesljiv. Ob kakršnikoli napaki API-ja
    (npr. manjka dovoljenje za branje objav) vrne False — raje morebitna
    dvojna objava kot izgubljena."""
    import datetime
    qs = urllib.parse.urlencode({"fields": "message,link,created_time", "limit": 50,
                                 "access_token": token})
    try:
        with urllib.request.urlopen(f"{GRAPH}/{page_id}/feed?{qs}", timeout=15) as r:
            items = json.load(r).get("data", [])
    except Exception as e:  # noqa: BLE001
        print(f"Facebook: preverjanje dvojnika ni uspelo ({e}) — objavljam.", file=sys.stderr)
        return False
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DEDUP_DAYS)
    first_line = message.split("\n", 1)[0].strip()
    for it in items:
        try:
            t = datetime.datetime.strptime(it["created_time"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if t < cutoff:
            continue
        link = (it.get("link") or "").split("?", 1)[0]
        text = (it.get("message") or "").strip()
        if (link and link == post_url) or (first_line and text.startswith(first_line)):
            return True
    return False


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

    if not os.environ.get("FB_FORCE") and already_posted(page_id, token, post_url, message):
        print(f"Facebook: članek {post['slug']} je že objavljen v zadnjih {DEDUP_DAYS} dneh — preskačem.")
        return 0

    mode = os.environ.get("FB_POST_MODE", "link").lower()

    if mode != "photo":
        try:
            body = post_link_only(page_id, token, message, with_utm(post_url, post["slug"]))
            print(f"Facebook: objavljeno (link) — {body}")
            return 0
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")[:300]
            print(f"Facebook: objava linka spodletela ({e.code}: {err}), poskušam s sliko …", file=sys.stderr)

    try:
        post_id = post_with_photo(page_id, token, post, message)
        print(f"Facebook: objavljeno (s sliko) — post_id={post_id}")
        try:
            post_link_comment(post_id, token, with_utm(post_url, post["slug"]))
            print("Facebook: link dodan kot prvi komentar.")
        except urllib.error.HTTPError as e:
            comment_err = e.read().decode("utf-8", "replace")[:300]
            print(f"Facebook: dodajanje linka v komentar spodletelo ({e.code}: {comment_err}).", file=sys.stderr)
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Facebook napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
