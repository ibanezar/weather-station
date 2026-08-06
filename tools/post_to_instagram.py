#!/usr/bin/env python3
"""
tools/post_to_instagram.py — objavi nov članek na Instagram računu (meteorec.si).

Instagram Graph API objavlja v dveh korakih: najprej ustvari "container"
(slika + podpis), nato ga potrdi z /media_publish. Uporablja OG sliko članka
(og/<slug>.jpg) -- enako sliko kot Facebook in Open Graph metapodatki.

IG_ACCESS_TOKEN je dolgotrajen (60 dni, izdan prek Instagram Business Login)
in ga je treba periodično osvežiti -- glej tools/ig_refresh_token.py.

Link do članka NI v caption -- objavi se ločeno kot prvi komentar (POST
/{media-id}/comments) po uspešni objavi, ker naj bi objave z linkom v
besedilu dosegle manjši organski doseg kot tiste brez.

Rabi okoljski spremenljivki IG_ACCOUNT_ID in IG_ACCESS_TOKEN (GitHub secreta).

Wired into: .github/workflows/daily-post.yml, monthly-post.yml,
storm-watch.yml, arso-newsjack.yml, invasive-watch.yml
(po uspešnem push-u novega članka na main).

Usage:
  python3 tools/post_to_instagram.py [slug]   # brez sluga: zadnji članek (blog.json[0])
"""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_JSON = os.path.join(ROOT, "blog.json")
SITE = "https://meteorec.si"
GRAPH = "https://graph.instagram.com/v21.0"

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
                    "Meteorca — uradna opozorila so na meteo.arso.gov.si/met/sl/warning/.")


def label_for(slug):
    for prefix, label in PREFIXES:
        if slug.startswith(prefix):
            return label
    return None


def build_caption(post):
    label = label_for(post["slug"])
    lines = [f"{label}: {post['title']}"] if label else [post["title"]]
    if post.get("summary"):
        lines.append(post["summary"])
    if post["slug"].startswith("arso-opozorilo-"):
        lines.append(ARSO_SOURCE_NOTE)
    lines.append("Cel članek: povezava je v prvem komentarju (in v bio).")
    if post.get("tags"):
        cleaned = (t.replace("-", "") for t in ("meteorec", "vreme", *post["tags"]))
        lines.append(" ".join(f"#{t}" for t in cleaned if t.isalnum()))
    return "\n\n".join(lines)


def api_post(path, **params):
    token = os.environ["IG_ACCESS_TOKEN"]
    payload = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    account_id = os.environ.get("IG_ACCOUNT_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not account_id or not token:
        print("IG_ACCOUNT_ID / IG_ACCESS_TOKEN nista nastavljena — preskačem objavo na Instagram.", file=sys.stderr)
        return 0

    posts = json.load(open(BLOG_JSON, encoding="utf-8"))
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    post = next((p for p in posts if p.get("slug") == slug), None) if slug else posts[0]
    if not post:
        print(f"Ni najdenega članka za objavo na Instagram (slug={slug!r}).", file=sys.stderr)
        return 1

    image_url = f"{SITE}/og/{post['slug']}.jpg"
    caption = build_caption(post)

    try:
        container = api_post(f"{account_id}/media", image_url=image_url, caption=caption)
        creation_id = container["id"]
        time.sleep(3)  # IG včasih rabi trenutek, da container obdela sliko
        result = api_post(f"{account_id}/media_publish", creation_id=creation_id)
        print(f"Instagram: objavljeno — {result}")
        media_id = result["id"]
        post_url = f"{SITE}{post['url']}"
        try:
            api_post(f"{media_id}/comments", message=f"Cel članek: {post_url}")
            print("Instagram: link dodan kot prvi komentar.")
        except urllib.error.HTTPError as e:
            comment_err = e.read().decode("utf-8", "replace")[:300]
            print(f"Instagram: dodajanje linka v komentar spodletelo ({e.code}: {comment_err}).", file=sys.stderr)
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        print(f"Instagram napaka {e.code}: {body}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
